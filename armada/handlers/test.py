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
from armada.exceptions.helm_exceptions import HelmCommandException
from armada.utils.release import label_selectors
from armada.utils.helm import is_test_pod

LOG = logging.getLogger(__name__)


class Test(object):
    def __init__(
            self,
            chart,
            release_id,
            helm,
            cg_test_charts=None,
            enable_all=False):
        """Initialize a test handler to run Helm tests corresponding to a
        release.

        :param chart: The armada chart document
        :param release_id: Id of a Helm release
        :param helm: helm object
        :param cg_test_charts: Chart group `test_charts` key
        :param enable_all: Run tests regardless of the value of `test.enabled`

        :type chart: dict
        :type release_id: HelmReleaseId
        :type helm: helm object
        :type cg_test_charts: bool
        :type enable_all: bool
        """

        self.chart = chart
        self.release_id = release_id
        self.helm = helm
        self.k8s_timeout = const.DEFAULT_K8S_TIMEOUT

        test_values = self.chart.get('test', None)

        self.timeout = const.DEFAULT_TEST_TIMEOUT

        # TODO: Remove when v1 doc support is removed.
        if cg_test_charts is not None:
            LOG.warn(
                'Chart group key `test_charts` is deprecated and will be '
                'removed. Use `test.enabled` instead.')
            self.test_enabled = cg_test_charts
        else:
            self.test_enabled = True

        # TODO: Remove when v1 doc support is removed.
        if (type(test_values) is bool):
            LOG.warn(
                'Boolean value for chart `test` key is deprecated and '
                'will be removed. Use `test.enabled` instead.')

            self.test_enabled = test_values

        elif test_values:
            test_enabled_opt = test_values.get('enabled')
            if test_enabled_opt is not None:
                self.test_enabled = test_enabled_opt

            self.timeout = test_values.get('timeout', self.timeout)

        if enable_all:
            self.test_enabled = True

    def test_release_for_success(self):
        """Run the Helm tests corresponding to a release for success (i.e. exit
        code 0).

        :return: Helm test suite run result
        """
        try:
            self.test_release()
        except HelmCommandException:
            return False
        return True

    def test_release(self):
        """Run the Helm tests corresponding to a release for success (i.e. exit
        code 0).

        :return: Helm test suite run result
        """
        LOG.info(
            'RUNNING: %s tests with timeout=%ds', self.release_id,
            self.timeout)

        try:
            self.delete_test_pods()
        except Exception:
            LOG.exception(
                "Exception when deleting test pods for release: %s",
                self.release_id)

        self.helm.test_release(self.release_id, timeout=self.timeout)

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

            pod_list = self.helm.k8s.client.list_namespaced_pod(**list_args)
            test_pods = [pod for pod in pod_list.items if is_test_pod(pod)]

            if test_pods:
                LOG.info(
                    'Found existing test pods for release with '
                    'namespace=%s, labels=(%s)', namespace, label_selector)

            for test_pod in test_pods:
                pod_name = test_pod.metadata.name
                LOG.info('Deleting existing test pod: %s', pod_name)
                self.helm.k8s.delete_pod_action(
                    pod_name, namespace, timeout=self.k8s_timeout)
