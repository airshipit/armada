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

from armada import const

TESTRUN_STATUS_UNKNOWN = 0
TESTRUN_STATUS_SUCCESS = 1
TESTRUN_STATUS_FAILURE = 2
TESTRUN_STATUS_RUNNING = 3

LOG = logging.getLogger(__name__)


class Test(object):

    def __init__(self,
                 release_name,
                 tiller,
                 cg_test_charts=None,
                 cleanup=None,
                 enable_all=False,
                 test_values=None):
        """Initialize a test handler to run Helm tests corresponding to a
        release.

        :param release_name: Name of a Helm release
        :param tiller: Tiller object
        :param cg_test_charts: Chart group `test_charts` key
        :param cleanup: Triggers cleanup; overrides `test.options.cleanup`
        :param enable_all: Run tests regardless of the value of `test.enabled`
        :param test_values: Test values retrieved from a chart's `test` key

        :type release_name: str
        :type tiller: Tiller object
        :type cg_test_charts: bool
        :type cleanup: bool
        :type enable_all: bool
        :type test_values: dict or bool (deprecated)
        """

        self.release_name = release_name
        self.tiller = tiller
        self.cleanup = cleanup

        # NOTE(drewwalters96): Support the chart_group `test_charts` key until
        # its deprecation period ends. The `test.enabled`, `enable_all` flag,
        # and deprecated, boolean `test` key override this value if provided.
        if cg_test_charts is not None:
            LOG.warn('Chart group key `test_charts` is deprecated and will be '
                     'removed. Use `test.enabled` instead.')
            self.test_enabled = cg_test_charts
        else:
            self.test_enabled = True

        # NOTE: Support old, boolean `test` key until deprecation period ends.
        if (type(test_values) == bool):
            LOG.warn('Boolean value for chart `test` key is deprecated and '
                     'will be removed. Use `test.enabled` instead.')

            self.test_enabled = test_values

            # NOTE: Use old, default cleanup value (i.e. True) if none is
            # provided.
            if self.cleanup is None:
                self.cleanup = True
        elif test_values:
            test_enabled_opt = test_values.get('enabled')
            if test_enabled_opt is not None:
                self.test_enabled = test_enabled_opt

            # NOTE(drewwalters96): `self.cleanup`, the cleanup value provided
            # by the API/CLI, takes precedence over the chart value
            # `test.cleanup`.
            if self.cleanup is None:
                test_options = test_values.get('options', {})
                self.cleanup = test_options.get('cleanup', False)
        else:
            # Default cleanup value
            if self.cleanup is None:
                self.cleanup = False

        if enable_all:
            self.test_enabled = True

    def test_release_for_success(self, timeout=const.DEFAULT_TILLER_TIMEOUT):
        """Run the Helm tests corresponding to a release for success (i.e. exit
        code 0).

        :param timeout: Timeout value for a release's tests completion
        :type timeout: int

        :rtype: Helm test suite run result
        """
        LOG.info('RUNNING: %s tests', self.release_name)

        test_suite_run = self.tiller.test_release(
            self.release_name, timeout=timeout, cleanup=self.cleanup)

        success = self.get_test_suite_run_success(test_suite_run)
        if success:
            LOG.info('PASSED: %s', self.release_name)
        else:
            LOG.info('FAILED: %s', self.release_name)

        return success

    @classmethod
    def get_test_suite_run_success(self, test_suite_run):
        return all(
            r.status == TESTRUN_STATUS_SUCCESS for r in test_suite_run.results)
