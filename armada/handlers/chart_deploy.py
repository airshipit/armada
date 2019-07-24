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

import time

from oslo_log import log as logging
import yaml

from armada import const
from armada.exceptions import armada_exceptions
from armada.handlers.chartbuilder import ChartBuilder
from armada.handlers.release_diff import ReleaseDiff
from armada.handlers.chart_delete import ChartDelete
from armada.handlers.schema import get_schema_info
from armada.handlers.test import Test
from armada.handlers.wait import ChartWait
from armada.exceptions import tiller_exceptions
import armada.utils.release as r

LOG = logging.getLogger(__name__)


class ChartDeploy(object):
    def __init__(
            self, disable_update_pre, disable_update_post, dry_run,
            k8s_wait_attempts, k8s_wait_attempt_sleep, timeout, tiller):
        self.disable_update_pre = disable_update_pre
        self.disable_update_post = disable_update_post
        self.dry_run = dry_run
        self.k8s_wait_attempts = k8s_wait_attempts
        self.k8s_wait_attempt_sleep = k8s_wait_attempt_sleep
        self.timeout = timeout
        self.tiller = tiller

    def execute(self, ch, cg_test_all_charts, prefix, known_releases):
        chart = ch[const.KEYWORD_DATA]
        namespace = chart.get('namespace')
        release = chart.get('release')
        release_name = r.release_prefixer(prefix, release)
        LOG.info('Processing Chart, release=%s', release_name)

        values = chart.get('values', {})
        pre_actions = {}
        post_actions = {}

        result = {}

        old_release = self.find_chart_release(known_releases, release_name)

        status = None
        if old_release:
            status = r.get_release_status(old_release)

        chart_wait = ChartWait(
            self.tiller.k8s,
            release_name,
            ch,
            namespace,
            k8s_wait_attempts=self.k8s_wait_attempts,
            k8s_wait_attempt_sleep=self.k8s_wait_attempt_sleep,
            timeout=self.timeout)

        native_wait_enabled = chart_wait.is_native_enabled()

        # Begin Chart timeout deadline
        deadline = time.time() + chart_wait.get_timeout()

        chartbuilder = ChartBuilder(ch)
        new_chart = chartbuilder.get_helm_chart()

        # TODO(mark-burnett): It may be more robust to directly call
        # tiller status to decide whether to install/upgrade rather
        # than checking for list membership.
        if status == const.STATUS_DEPLOYED:

            # indicate to the end user what path we are taking
            LOG.info(
                "Existing release %s found in namespace %s", release_name,
                namespace)

            # extract the installed chart and installed values from the
            # latest release so we can compare to the intended state
            old_chart = old_release.chart
            old_values_string = old_release.config.raw

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
            recreate_pods = options.get('recreate_pods', False)

            if upgrade:
                upgrade_pre = upgrade.get('pre', {})
                upgrade_post = upgrade.get('post', {})

                if not self.disable_update_pre and upgrade_pre:
                    pre_actions = upgrade_pre

                if not self.disable_update_post and upgrade_post:
                    LOG.warning(
                        'Post upgrade actions are ignored by Armada'
                        'and will not affect deployment.')
                    post_actions = upgrade_post

            try:
                old_values = yaml.safe_load(old_values_string)
            except yaml.YAMLError:
                chart_desc = '{} (previously deployed)'.format(
                    old_chart.metadata.name)
                raise armada_exceptions.\
                    InvalidOverrideValuesYamlException(chart_desc)

            LOG.info('Checking for updates to chart release inputs.')
            diff = self.get_diff(old_chart, old_values, new_chart, values)

            if not diff:
                LOG.info("Found no updates to chart release inputs")
            else:
                LOG.info("Found updates to chart release inputs")
                LOG.debug("%s", diff)
                result['diff'] = {chart['release']: str(diff)}

                # TODO(MarshM): Add tiller dry-run before upgrade and
                # consider deadline impacts

                # do actual update
                timer = int(round(deadline - time.time()))
                LOG.info(
                    "Upgrading release %s in namespace %s, wait=%s, "
                    "timeout=%ss", release_name, namespace,
                    native_wait_enabled, timer)
                tiller_result = self.tiller.update_release(
                    new_chart,
                    release_name,
                    namespace,
                    pre_actions=pre_actions,
                    post_actions=post_actions,
                    disable_hooks=disable_hooks,
                    values=yaml.safe_dump(values),
                    wait=native_wait_enabled,
                    timeout=timer,
                    force=force,
                    recreate_pods=recreate_pods)

                LOG.info(
                    'Upgrade completed with results from Tiller: %s',
                    tiller_result.__dict__)
                result['upgrade'] = release_name
        else:
            # Check for release with status other than DEPLOYED
            if status:
                if status != const.STATUS_FAILED:
                    LOG.warn(
                        'Unexpected release status encountered '
                        'release=%s, status=%s', release_name, status)

                    # Make best effort to determine whether a deployment is
                    # likely pending, by checking if the last deployment
                    # was started within the timeout window of the chart.
                    last_deployment_age = r.get_last_deployment_age(
                        old_release)
                    wait_timeout = chart_wait.get_timeout()
                    likely_pending = last_deployment_age <= wait_timeout
                    if likely_pending:
                        # Give up if a deployment is likely pending, we do not
                        # want to have multiple operations going on for the
                        # same release at the same time.
                        raise armada_exceptions.\
                            DeploymentLikelyPendingException(
                                release_name, status, last_deployment_age,
                                wait_timeout)
                    else:
                        # Release is likely stuck in an unintended (by tiller)
                        # state. Log and continue on with remediation steps
                        # below.
                        LOG.info(
                            'Old release %s likely stuck in status %s, '
                            '(last deployment age=%ss) >= '
                            '(chart wait timeout=%ss)', release, status,
                            last_deployment_age, wait_timeout)

                protected = chart.get('protected', {})
                if protected:
                    p_continue = protected.get('continue_processing', False)
                    if p_continue:
                        LOG.warn(
                            'Release %s is `protected`, '
                            'continue_processing=True. Operator must '
                            'handle %s release manually.', release_name,
                            status)
                        result['protected'] = release_name
                        return result
                    else:
                        LOG.error(
                            'Release %s is `protected`, '
                            'continue_processing=False.', release_name)
                        raise armada_exceptions.ProtectedReleaseException(
                            release_name, status)
                else:
                    # Purge the release
                    LOG.info(
                        'Purging release %s with status %s', release_name,
                        status)
                    chart_delete = ChartDelete(
                        chart, release_name, self.tiller)
                    chart_delete.delete()
                    result['purge'] = release_name

            timer = int(round(deadline - time.time()))
            LOG.info(
                "Installing release %s in namespace %s, wait=%s, "
                "timeout=%ss", release_name, namespace, native_wait_enabled,
                timer)
            tiller_result = self.tiller.install_release(
                new_chart,
                release_name,
                namespace,
                values=yaml.safe_dump(values),
                wait=native_wait_enabled,
                timeout=timer)

            LOG.info(
                'Install completed with results from Tiller: %s',
                tiller_result.__dict__)
            result['install'] = release_name

        # Wait
        timer = int(round(deadline - time.time()))
        chart_wait.wait(timer)

        # Test
        just_deployed = ('install' in result) or ('upgrade' in result)
        last_test_passed = old_release and r.get_last_test_result(old_release)

        test_handler = Test(
            chart,
            release_name,
            self.tiller,
            cg_test_charts=cg_test_all_charts)

        run_test = test_handler.test_enabled and (
            just_deployed or not last_test_passed)
        if run_test:
            self._test_chart(release_name, test_handler)

        return result

    def _test_chart(self, release_name, test_handler):
        if self.dry_run:
            LOG.info(
                'Skipping test during `dry-run`, would have tested '
                'release=%s', release_name)
            return True

        success = test_handler.test_release_for_success()
        if not success:
            raise tiller_exceptions.TestFailedException(release_name)

    def get_diff(self, old_chart, old_values, new_chart, values):
        return ReleaseDiff(old_chart, old_values, new_chart, values).get_diff()

    def find_chart_release(self, known_releases, release_name):
        '''
        Find a release given a list of known_releases and a release name
        '''
        for release in known_releases:
            if release.name == release_name:
                return release
        LOG.info(
            "known: %s, release_name: %s",
            list(map(lambda r: r.name, known_releases)), release_name)
        return None
