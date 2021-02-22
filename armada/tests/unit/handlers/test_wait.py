# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

import mock

from armada import const
from armada.exceptions import manifest_exceptions
from armada.handlers import wait
from armada.tests.unit import base

test_chart = {'wait': {'timeout': 10, 'native': {'enabled': False}}}


class ChartWaitTestCase(base.ArmadaTestCase):
    def get_unit(self, chart_data, timeout=None, version=2):
        chart = {
            'schema': 'armada/Chart/v{}'.format(str(version)),
            'metadata': {
                'name': 'test'
            },
            const.KEYWORD_DATA: chart_data
        }
        return wait.ChartWait(
            k8s=mock.MagicMock(),
            release_name='test-test',
            chart=chart,
            namespace='test',
            k8s_wait_attempts=1,
            k8s_wait_attempt_sleep=1,
            timeout=timeout)

    def test_get_timeout(self):
        unit = self.get_unit({'timeout': 5, 'wait': {'timeout': 10}})
        self.assertEquals(unit.get_timeout(), 10)

    def test_get_timeout_default(self):
        unit = self.get_unit({})
        self.assertEquals(unit.get_timeout(), const.DEFAULT_CHART_TIMEOUT)

    def test_get_timeout_override(self):
        unit = self.get_unit(
            timeout=20, chart_data={
                'timeout': 5,
                'wait': {
                    'timeout': 10
                }
            })

        self.assertEquals(unit.get_timeout(), 20)

    def test_get_timeout_deprecated(self):
        unit = self.get_unit({'timeout': 5})
        self.assertEquals(unit.get_timeout(), 5)

    def test_is_native_enabled_default_false(self):
        unit = self.get_unit({})
        self.assertEquals(unit.is_native_enabled(), False)

    def test_is_native_enabled_true(self):
        unit = self.get_unit({'wait': {'native': {'enabled': True}}})
        self.assertEquals(unit.is_native_enabled(), True)

    def test_is_native_enabled_false(self):
        unit = self.get_unit({'wait': {'native': {'enabled': False}}})
        self.assertEquals(unit.is_native_enabled(), False)

    def test_waits_init(self):
        unit = self.get_unit({
            'wait': {
                'resources': [{
                    'type': 'pod',
                    'labels': {
                        'foo': 'bar'
                    }
                }, {
                    'type': 'job',
                    'labels': {
                        'foo': 'bar'
                    }
                }, {
                    'type': 'daemonset',
                    'labels': {
                        'foo': 'bar'
                    },
                    'min_ready': 5
                }, {
                    'type': 'deployment',
                    'labels': {
                        'foo': 'bar'
                    },
                    'min_ready': '50%'
                }, {
                    'type': 'statefulset',
                    'labels': {
                        'foo': 'bar'
                    }
                }]
            }
        })  # yapf: disable

        self.assertEqual(5, len(unit.waits))
        self.assertIsInstance(unit.waits[0], wait.PodWait)
        self.assertIsInstance(unit.waits[1], wait.JobWait)
        self.assertIsInstance(unit.waits[2], wait.DaemonSetWait)
        self.assertIsInstance(unit.waits[3], wait.DeploymentWait)
        self.assertIsInstance(unit.waits[4], wait.StatefulSetWait)

    def test_waits_init_min_ready_fails_if_not_controller(self):
        def create_pod_wait_min_ready():
            self.get_unit(
                {
                    'wait': {
                        'resources': [
                            {
                                'type': 'pod',
                                'labels': {
                                    'foo': 'bar'
                                },
                                'min_ready': 5
                            }
                        ]
                    }
                })

        self.assertRaises(
            manifest_exceptions.ManifestException, create_pod_wait_min_ready)

        def create_job_wait_min_ready():
            self.get_unit(
                {
                    'wait': {
                        'resources': [
                            {
                                'type': 'job',
                                'labels': {
                                    'foo': 'bar'
                                },
                                'min_ready': 5
                            }
                        ]
                    }
                })

        self.assertRaises(
            manifest_exceptions.ManifestException, create_job_wait_min_ready)

    def test_waits_init_invalid_type(self):
        def create_with_invalid_type():
            self.get_unit(
                {
                    'wait': {
                        'resources': [
                            {
                                'type': 'invalid',
                                'labels': {
                                    'foo': 'bar'
                                },
                                'min_ready': 5
                            }
                        ]
                    }
                })

        self.assertRaises(
            manifest_exceptions.ManifestException, create_with_invalid_type)

    @mock.patch.object(wait.ChartWait, 'get_resource_wait')
    def test_wait(self, get_resource_wait):
        def return_mock(*args, **kwargs):
            return mock.MagicMock()

        get_resource_wait.side_effect = return_mock

        unit = self.get_unit(
            {'wait': {
                'resources': [{
                    'type': 'foo'
                }, {
                    'type': 'bar'
                }]
            }})

        unit.wait(10)

        self.assertEqual(2, len(unit.waits))
        for w in unit.waits:
            w.wait.assert_called_once()


class PodWaitTestCase(base.ArmadaTestCase):
    def get_unit(self, labels, version=2):
        return wait.PodWait(
            resource_type='pod',
            chart_wait=ChartWaitTestCase.get_unit(None, {}, version=version),
            labels=labels)

    def test_include_resource(self):
        def mock_resource(annotations={}, owner_references=None):
            resource = mock.Mock()
            resource.metadata.annotations = annotations
            resource.metadata.owner_references = owner_references
            return resource

        test_pods = [
            mock_resource({
                'key': 'value',
                'helm.sh/hook': 'test-success'
            }),
            mock_resource({'helm.sh/hook': 'test-failure'}),
            mock_resource({'helm.sh/hook': 'test-success,pre-install'}),
        ]
        job_pods = [
            mock_resource(owner_references=[mock.Mock(kind='Job')]),
            mock_resource(
                owner_references=[
                    mock.Mock(kind='NotAJob'),
                    mock.Mock(kind='Job')
                ])
        ]
        included_pods = [
            mock_resource(),
            mock_resource(owner_references=[]),
            mock_resource({'helm.sh/hook': 'pre-install'}),
            mock_resource({'key': 'value'}),
            mock_resource(owner_references=[mock.Mock(kind='NotAJob')]),
        ]
        evicted_pods = [
            mock.Mock(
                metadata=mock.Mock(annotations={}, owner_references=None),
                status=mock.Mock(phase='Evicted')),
        ]

        unit = self.get_unit({}, version=1)

        # Validate test pods excluded
        for pod in test_pods:
            self.assertFalse(unit.include_resource(pod))

        # Validate test pods excluded
        for pod in job_pods:
            self.assertFalse(unit.include_resource(pod))

        # Validate other resources included
        for pod in included_pods:
            self.assertTrue(unit.include_resource(pod))

        # Validate evicted pods are excluded
        for pod in evicted_pods:
            self.assertFalse(unit.include_resource(pod))


class JobWaitTestCase(base.ArmadaTestCase):
    def get_unit(self, labels):
        return wait.JobWait(
            resource_type='job', chart_wait=mock.MagicMock(), labels=labels)

    def test_include_resource(self):
        def mock_resource(annotations={}, owner_references=None):
            resource = mock.Mock()
            resource.metadata.annotations = annotations
            resource.metadata.owner_references = owner_references
            return resource

        cronjob_jobs = [
            mock_resource(owner_references=[mock.Mock(kind='CronJob')]),
            mock_resource(
                owner_references=[
                    mock.Mock(kind='NotACronJob'),
                    mock.Mock(kind='CronJob')
                ])
        ]
        included_jobs = [
            mock_resource(),
            mock_resource(owner_references=[]),
            mock_resource(owner_references=[mock.Mock(kind='NotAJob')])
        ]

        unit = self.get_unit({})

        # Validate test pods excluded
        for job in cronjob_jobs:
            self.assertFalse(unit.include_resource(job))

        # Validate other resources included
        for job in included_jobs:
            self.assertTrue(unit.include_resource(job))
