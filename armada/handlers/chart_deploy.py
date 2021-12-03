# Copyright 2018 The Armada Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time

from oslo_log import log as logging

from armada import const
from armada.exceptions import armada_exceptions
from armada.handlers import metrics
from armada.handlers.chartbuilder import ChartBuilder
from armada.handlers import helm
from armada.handlers.release_diff import ReleaseDiff
from armada.handlers.chart_delete import ChartDelete
from armada.handlers.pre_update_actions import PreUpdateActions
from armada.handlers.schema import get_schema_info
from armada.handlers.test import Test
from armada.handlers.wait import ChartWait
import armada.utils.release as r

LOG = logging.getLogger(__name__)


class ChartDeploy(object):
    def __init__(
            self, manifest, disable_update_pre, disable_update_post,
            k8s_wait_attempts, k8s_wait_attempt_sleep, timeout, helm):
        self.manifest = manifest
        self.disable_update_pre = disable_update_pre
        self.disable_update_post = disable_update_post
        self.k8s_wait_attempts = k8s_wait_attempts
        self.k8s_wait_attempt_sleep = k8s_wait_attempt_sleep
        self.timeout = timeout
        self.helm = helm

    def execute(self, ch, cg_test_all_charts, prefix, concurrency):
        chart_name = ch['metadata']['name']
        manifest_name = self.manifest['metadata']['name']
        with metrics.CHART_HANDLE.get_context(concurrency, manifest_name,
                                              chart_name):
            return self._execute(ch, cg_test_all_charts, prefix)

    def _execute(self, ch, cg_test_all_charts, prefix):
        manifest_name = self.manifest['metadata']['name']
        chart = ch[const.KEYWORD_DATA]
        chart_name = ch['metadata']['name']
        namespace = chart.get('namespace')
        release = chart.get('release')
        release_name = r.release_prefixer(prefix, release)
        release_id = helm.HelmReleaseId(namespace, release_name)
        source_dir = chart['source_dir']
        source_directory = os.path.join(*source_dir)
        LOG.info('Processing Chart, release=%s', release_id)

        result = {}

        chart_wait = ChartWait(
            self.helm.k8s,
            release_id,
            ch,
            k8s_wait_attempts=self.k8s_wait_attempts,
            k8s_wait_attempt_sleep=self.k8s_wait_attempt_sleep,
            timeout=self.timeout)
        wait_timeout = chart_wait.get_timeout()

        # Begin Chart timeout deadline
        deadline = time.time() + wait_timeout
        old_release = self.helm.release_metadata(release_id)
        action = metrics.ChartDeployAction.NOOP

        def noop():
            pass

        deploy = noop

        # Resolve action
        values = chart.get('values', {})
        pre_actions = {}

        status = None
        if old_release:
            status = r.get_release_status(old_release)

        native_wait_enabled = chart_wait.is_native_enabled()

        chartbuilder = ChartBuilder.from_chart_doc(ch, self.helm)

        if status == helm.STATUS_DEPLOYED:

            # indicate to the end user what path we are taking
            LOG.info("Existing release %s found", release_id)

            # extract the installed chart and installed values from the
            # latest release so we can compare to the intended state
            old_chart = old_release['chart']
            old_values = old_release.get('config', {})

            upgrade = chart.get('upgrade', {})
            options = upgrade.get('options', {})

            # TODO: Remove when v1 doc support is removed.
            schema_info = get_schema_info(ch['schema'])
            if schema_info.version < 2:
                no_hooks_location = upgrade
            else:
                no_hooks_location = options

            disable_hooks = no_hooks_location.get('no_hooks', False)
            force = options.get('force', False)

            if upgrade:
                upgrade_pre = upgrade.get('pre', {})
                upgrade_post = upgrade.get('post', {})

                if not self.disable_update_pre and upgrade_pre:
                    pre_actions = upgrade_pre

                if not self.disable_update_post and upgrade_post:
                    LOG.warning(
                        'Post upgrade actions are ignored by Armada'
                        'and will not affect deployment.')

            LOG.info('Checking for updates to chart release inputs.')
            new_chart = chartbuilder.get_helm_chart(release_id, values)
            diff = self.get_diff(old_chart, old_values, new_chart, values)

            if not diff:
                LOG.info("Found no updates to chart release inputs")
            else:
                action = metrics.ChartDeployAction.UPGRADE
                LOG.info("Found updates to chart release inputs")
                result['diff'] = {chart['release']: str(diff)}

                def upgrade():
                    # do actual update
                    timer = int(round(deadline - time.time()))
                    PreUpdateActions(self.helm.k8s).execute(
                        pre_actions, release, namespace, chart, disable_hooks,
                        values, timer)
                    LOG.info(
                        "Upgrading release=%s, wait=%s, "
                        "timeout=%ss", release_id, native_wait_enabled, timer)
                    self.helm.upgrade_release(
                        source_directory,
                        release_id,
                        disable_hooks=disable_hooks,
                        values=values,
                        wait=native_wait_enabled,
                        timeout=timer,
                        force=force)

                    LOG.info('Upgrade completed')
                    result['upgrade'] = release_id

                deploy = upgrade
        else:

            def install():
                timer = int(round(deadline - time.time()))
                LOG.info(
                    "Installing release=%s, wait=%s, "
                    "timeout=%ss", release_id, native_wait_enabled, timer)
                self.helm.install_release(
                    source_directory,
                    release_id,
                    values=values,
                    wait=native_wait_enabled,
                    timeout=timer)

                LOG.info('Install completed')
                result['install'] = release_id

            # Check for release with status other than DEPLOYED
            if status:
                if status != helm.STATUS_FAILED:
                    LOG.warn(
                        'Unexpected release status encountered '
                        'release=%s, status=%s', release_id, status)

                    # Make best effort to determine whether a deployment is
                    # likely pending, by checking if the last deployment
                    # was started within the timeout window of the chart.
                    last_deployment_age = r.get_last_deployment_age(
                        old_release)
                    likely_pending = last_deployment_age <= wait_timeout
                    if likely_pending:
                        # We don't take any deploy action and wait for the
                        # to get deployed.
                        deploy = noop
                        deadline = deadline - last_deployment_age
                    else:
                        # Release is likely stuck in an unintended
                        # state. Log and continue on with remediation steps
                        # below.
                        LOG.info(
                            'Old release %s likely stuck in status %s, '
                            '(last deployment age=%ss) >= '
                            '(chart wait timeout=%ss)', release, status,
                            last_deployment_age, wait_timeout)
                        res = self.purge_release(
                            chart, release_id, status, manifest_name,
                            chart_name, result)
                        if isinstance(res, dict):
                            if 'protected' in res:
                                return res
                        action = metrics.ChartDeployAction.INSTALL
                        deploy = install
                else:
                    # The chart is in Failed state, hence we purge
                    # the chart and attempt to install it again.
                    res = self.purge_release(
                        chart, release_id, status, manifest_name, chart_name,
                        result)
                    if isinstance(res, dict):
                        if 'protected' in res:
                            return res
                    action = metrics.ChartDeployAction.INSTALL
                    deploy = install

        if status is None:
            action = metrics.ChartDeployAction.INSTALL
            deploy = install

        # Deploy
        with metrics.CHART_DEPLOY.get_context(wait_timeout, manifest_name,
                                              chart_name,
                                              action.get_label_value()):
            deploy()

            # Wait
            timer = int(round(deadline - time.time()))
            chart_wait.wait(timer)

        # Test
        just_deployed = ('install' in result) or ('upgrade' in result)
        last_test_passed = old_release and r.get_last_test_result(old_release)

        test_handler = Test(
            chart, release_id, self.helm, cg_test_charts=cg_test_all_charts)

        run_test = test_handler.test_enabled and (
            just_deployed or not last_test_passed)
        if run_test:
            with metrics.CHART_TEST.get_context(test_handler.timeout,
                                                manifest_name, chart_name):
                self._test_chart(test_handler)

        return result

    def purge_release(
            self, chart, release_id, status, manifest_name, chart_name,
            result):
        protected = chart.get('protected', {})
        if protected:
            p_continue = protected.get('continue_processing', False)
            if p_continue:
                LOG.warn(
                    'Release %s is `protected`, '
                    'continue_processing=True. Operator must '
                    'handle %s release manually.', release_id, status)
                result['protected'] = release_id
                return result
            else:
                LOG.error(
                    'Release %s is `protected`, '
                    'continue_processing=False.', release_id)
                raise armada_exceptions.ProtectedReleaseException(
                    release_id, status)
        else:
            # Purge the release
            with metrics.CHART_DELETE.get_context(manifest_name, chart_name):

                LOG.info(
                    'Purging release %s with status %s', release_id, status)
                chart_delete = ChartDelete(chart, release_id, self.helm)
                chart_delete.delete()
                result['purge'] = release_id

    def _test_chart(self, test_handler):
        test_handler.test_release()

    def get_diff(self, old_chart, old_values, new_chart, values):
        return ReleaseDiff(old_chart, old_values, new_chart, values).get_diff()
