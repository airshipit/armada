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

from oslo_log import log as logging
import time
import yaml

from armada import const
from armada.exceptions import armada_exceptions
from armada.handlers.chartbuilder import ChartBuilder
from armada.handlers.test import test_release_for_success
from armada.handlers.release_diff import ReleaseDiff
from armada.handlers.wait import ChartWait
from armada.exceptions import tiller_exceptions
import armada.utils.release as r

LOG = logging.getLogger(__name__)


class ChartDeploy(object):

    def __init__(self, disable_update_pre, disable_update_post, dry_run,
                 k8s_wait_attempts, k8s_wait_attempt_sleep, timeout, tiller):
        self.disable_update_pre = disable_update_pre
        self.disable_update_post = disable_update_post
        self.dry_run = dry_run
        self.k8s_wait_attempts = k8s_wait_attempts
        self.k8s_wait_attempt_sleep = k8s_wait_attempt_sleep
        self.timeout = timeout
        self.tiller = tiller

    def execute(self, chart, cg_test_all_charts, prefix, known_releases):
        namespace = chart.get('namespace')
        release = chart.get('release')
        release_name = r.release_prefixer(prefix, release)
        LOG.info('Processing Chart, release=%s', release_name)

        values = chart.get('values', {})
        pre_actions = {}
        post_actions = {}

        result = {}

        protected = chart.get('protected', {})
        p_continue = protected.get('continue_processing', False)

        old_release = self.find_chart_release(known_releases, release_name)

        status = None
        if old_release:
            status = r.get_release_status(old_release)

            if status not in [const.STATUS_FAILED, const.STATUS_DEPLOYED]:
                raise armada_exceptions.UnexpectedReleaseStatusException(
                    release_name, status)

        chart_wait = ChartWait(
            self.tiller.k8s,
            release_name,
            chart,
            namespace,
            k8s_wait_attempts=self.k8s_wait_attempts,
            k8s_wait_attempt_sleep=self.k8s_wait_attempt_sleep,
            timeout=self.timeout)

        native_wait_enabled = chart_wait.is_native_enabled()

        # Begin Chart timeout deadline
        deadline = time.time() + chart_wait.get_timeout()

        chartbuilder = ChartBuilder(chart)
        new_chart = chartbuilder.get_helm_chart()

        # Check for existing FAILED release, and purge
        if status == const.STATUS_FAILED:
            LOG.info('Purging FAILED release %s before deployment.',
                     release_name)
            if protected:
                if p_continue:
                    LOG.warn(
                        'Release %s is `protected`, '
                        'continue_processing=True. Operator must '
                        'handle FAILED release manually.', release_name)
                    result['protected'] = release_name
                    return result
                else:
                    LOG.error(
                        'Release %s is `protected`, '
                        'continue_processing=False.', release_name)
                    raise armada_exceptions.ProtectedReleaseException(
                        release_name)
            else:
                # Purge the release
                self.tiller.uninstall_release(release_name)
                result['purge'] = release_name

        # TODO(mark-burnett): It may be more robust to directly call
        # tiller status to decide whether to install/upgrade rather
        # than checking for list membership.
        if status == const.STATUS_DEPLOYED:

            # indicate to the end user what path we are taking
            LOG.info("Existing release %s found in namespace %s", release_name,
                     namespace)

            # extract the installed chart and installed values from the
            # latest release so we can compare to the intended state
            old_chart = old_release.chart
            old_values_string = old_release.config.raw

            upgrade = chart.get('upgrade', {})
            disable_hooks = upgrade.get('no_hooks', False)
            force = upgrade.get('force', False)
            recreate_pods = upgrade.get('recreate_pods', False)

            if upgrade:
                upgrade_pre = upgrade.get('pre', {})
                upgrade_post = upgrade.get('post', {})

                if not self.disable_update_pre and upgrade_pre:
                    pre_actions = upgrade_pre

                if not self.disable_update_post and upgrade_post:
                    LOG.warning('Post upgrade actions are ignored by Armada'
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

                LOG.info('Upgrade completed with results from Tiller: %s',
                         tiller_result.__dict__)
                result['upgrade'] = release_name
        else:
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

            LOG.info('Install completed with results from Tiller: %s',
                     tiller_result.__dict__)
            result['install'] = release_name

        # Wait
        timer = int(round(deadline - time.time()))
        chart_wait.wait(timer)

        # Test
        test_chart_override = chart.get('test')
        # Use old default value when not using newer `test` key
        test_cleanup = True
        if test_chart_override is None:
            test_enabled = cg_test_all_charts
        elif isinstance(test_chart_override, bool):
            LOG.warn('Boolean value for chart `test` key is'
                     ' deprecated and support for this will'
                     ' be removed. Use `test.enabled` '
                     'instead.')
            test_enabled = test_chart_override
        else:
            # NOTE: helm tests are enabled by default
            test_enabled = test_chart_override.get('enabled', True)
            test_cleanup = test_chart_override.get('options', {}).get(
                'cleanup', False)

        just_deployed = ('install' in result) or ('upgrade' in result)
        last_test_passed = old_release and r.get_last_test_result(old_release)
        run_test = test_enabled and (just_deployed or not last_test_passed)

        if run_test:
            timer = int(round(deadline - time.time()))
            self._test_chart(release_name, timer, test_cleanup)

        return result

    def _test_chart(self, release_name, timeout, cleanup):
        if self.dry_run:
            LOG.info(
                'Skipping test during `dry-run`, would have tested '
                'release=%s with timeout %ss.', release_name, timeout)
            return True

        if timeout <= 0:
            reason = ('Timeout expired before testing '
                      'release %s' % release_name)
            LOG.error(reason)
            raise armada_exceptions.ArmadaTimeoutException(reason)

        success = test_release_for_success(
            self.tiller, release_name, timeout=timeout, cleanup=cleanup)
        if success:
            LOG.info("Test passed for release: %s", release_name)
        else:
            LOG.info("Test failed for release: %s", release_name)
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
        LOG.info("known: %s, release_name: %s",
                 list(map(lambda r: r.name, known_releases)), release_name)
        return None
