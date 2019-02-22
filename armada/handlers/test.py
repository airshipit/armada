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

from armada.handlers.wait import get_wait_labels
from armada.utils.release import label_selectors
from armada.utils.helm import get_test_suite_run_success, is_test_pod

LOG = logging.getLogger(__name__)


class Test(object):

    def __init__(self,
                 chart,
                 release_name,
                 tiller,
                 cg_test_charts=None,
                 cleanup=None,
                 enable_all=False):
        """Initialize a test handler to run Helm tests corresponding to a
        release.

        :param chart: The armada chart document
        :param release_name: Name of a Helm release
        :param tiller: Tiller object
        :param cg_test_charts: Chart group `test_charts` key
        :param cleanup: Triggers cleanup; overrides `test.options.cleanup`
        :param enable_all: Run tests regardless of the value of `test.enabled`

        :type chart: dict
        :type release_name: str
        :type tiller: Tiller object
        :type cg_test_charts: bool
        :type cleanup: bool
        :type enable_all: bool
        """

        self.chart = chart
        self.release_name = release_name
        self.tiller = tiller
        self.cleanup = cleanup
        self.k8s_timeout = const.DEFAULT_K8S_TIMEOUT

        test_values = self.chart.get('test', None)

        self.timeout = const.DEFAULT_TEST_TIMEOUT

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

            self.timeout = test_values.get('timeout', self.timeout)
        else:
            # Default cleanup value
            if self.cleanup is None:
                self.cleanup = False

        if enable_all:
            self.test_enabled = True

    def test_release_for_success(self):
        """Run the Helm tests corresponding to a release for success (i.e. exit
        code 0).

        :return: Helm test suite run result
        """
        LOG.info('RUNNING: %s tests with timeout=%ds', self.release_name,
                 self.timeout)

        try:
            self.delete_test_pods()
        except Exception:
            LOG.exception("Exception when deleting test pods for release: %s",
                          self.release_name)

        test_suite_run = self.tiller.test_release(
            self.release_name, timeout=self.timeout, cleanup=self.cleanup)

        success = get_test_suite_run_success(test_suite_run)
        if success:
            LOG.info('PASSED: %s', self.release_name)
        else:
            LOG.info('FAILED: %s', self.release_name)

        return success

    def delete_test_pods(self):
        """Deletes any existing test pods for the release, as identified by the
        wait labels for the chart, to avoid test pod name conflicts when
        creating the new test pod as well as just for general cleanup since
        the new test pod should supercede it.
        """
        labels = get_wait_labels(self.chart)

        # Guard against labels being left empty, so we don't delete other
        # chart's test pods.
        if labels:
            label_selector = label_selectors(labels)

            namespace = self.chart['namespace']

            list_args = {
                'namespace': namespace,
                'label_selector': label_selector,
                'timeout_seconds': self.k8s_timeout
            }

            pod_list = self.tiller.k8s.client.list_namespaced_pod(**list_args)
            test_pods = [pod for pod in pod_list.items if is_test_pod(pod)]

            if test_pods:
                LOG.info(
                    'Found existing test pods for release with '
                    'namespace=%s, labels=(%s)', namespace, label_selector)

            for test_pod in test_pods:
                pod_name = test_pod.metadata.name
                LOG.info('Deleting existing test pod: %s', pod_name)
                self.tiller.k8s.delete_pod_action(
                    pod_name, namespace, timeout=self.k8s_timeout)
