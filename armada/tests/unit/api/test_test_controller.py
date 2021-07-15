# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os

import mock
import yaml

from armada import api
from armada.api.controller import test
from armada.common.policies import base as policy_base
from armada.exceptions import manifest_exceptions
from armada.tests import test_utils
from armada.tests.unit.api import base


@mock.patch.object(
    test.TestReleasesManifestController, 'handle',
    test.TestReleasesManifestController.handle.__wrapped__)
class TestReleasesManifestControllerTest(base.BaseControllerTest):
    @mock.patch.object(test, 'Manifest')
    @mock.patch.object(api, 'Helm')
    def test_test_controller_with_manifest(self, mock_Helm, mock_manifest):
        rules = {'armada:test_manifest': '@'}
        self.policy.set_rules(rules)

        # TODO: Don't use example charts in tests.
        manifest_path = os.path.join(
            os.getcwd(), 'examples', 'keystone-manifest.yaml')
        with open(manifest_path, 'r') as f:
            payload = f.read()
        documents = list(yaml.safe_load_all(payload))

        m_helm = mock_Helm.return_value
        m_helm.__enter__.return_value = m_helm

        resp = self.app.simulate_post('/api/v1.0/tests', body=payload)
        self.assertEqual(200, resp.status_code)

        result = json.loads(resp.text)
        expected = {"tests": {"passed": [], "skipped": [], "failed": []}}
        self.assertEqual(expected, result)

        mock_manifest.assert_called_once_with(documents, target_manifest=None)
        mock_Helm.assert_called()
        m_helm.__exit__.assert_called()


@mock.patch.object(
    test.TestReleasesReleaseNameController, 'handle',
    test.TestReleasesReleaseNameController.handle.__wrapped__)
class TestReleasesReleaseNameControllerTest(base.BaseControllerTest):
    @mock.patch.object(test.Test, 'test_release_for_success')
    @mock.patch.object(api, 'Helm')
    def test_test_controller_test_pass(
            self, mock_Helm, mock_test_release_for_success):
        rules = {'armada:test_release': '@'}
        self.policy.set_rules(rules)

        mock_test_release_for_success.return_value = True

        m_helm = mock_Helm.return_value
        m_helm.__enter__.return_value = m_helm

        namespace = 'fake-namespace'
        release = 'fake-release'
        resp = self.app.simulate_get(
            '/api/v1.0/test/{}/{}'.format(namespace, release))
        mock_test_release_for_success.assert_called_once()
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            'MESSAGE: Test Pass',
            json.loads(resp.text)['message'])
        m_helm.__exit__.assert_called()

    @mock.patch.object(test.Test, 'test_release_for_success')
    @mock.patch.object(api, 'Helm')
    def test_test_controller_test_fail(
            self, mock_Helm, mock_test_release_for_success):
        rules = {'armada:test_release': '@'}
        self.policy.set_rules(rules)

        m_helm = mock_Helm.return_value
        m_helm.__enter__.return_value = m_helm

        mock_test_release_for_success.return_value = False
        namespace = 'fake-namespace'
        release = 'fake-release'
        resp = self.app.simulate_get(
            '/api/v1.0/test/{}/{}'.format(namespace, release))
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            'MESSAGE: Test Fail',
            json.loads(resp.text)['message'])
        m_helm.__exit__.assert_called()


@test_utils.attr(type=['negative'])
@mock.patch.object(
    test.TestReleasesManifestController, 'handle',
    test.TestReleasesManifestController.handle.__wrapped__)
class TestReleasesManifestControllerNegativeTest(base.BaseControllerTest):
    @mock.patch.object(test, 'Manifest')
    @mock.patch.object(api, 'Helm')
    @mock.patch.object(test.Test, 'test_release_for_success')
    def test_test_controller_Helm_exc_returns_500(
            self, mock_test_release_for_success, mock_Helm, _):
        rules = {'armada:test_manifest': '@'}
        self.policy.set_rules(rules)

        mock_Helm.side_effect = Exception
        mock_test_release_for_success.side_effect = Exception

        resp = self.app.simulate_post('/api/v1.0/tests')
        self.assertEqual(500, resp.status_code)

    @mock.patch.object(test, 'Manifest')
    @mock.patch.object(api, 'Helm')
    def test_test_controller_validation_failure_returns_400(
            self, mock_Helm, mock_manifest):
        rules = {'armada:test_manifest': '@'}
        self.policy.set_rules(rules)

        manifest_path = os.path.join(
            os.getcwd(), 'examples', 'keystone-manifest.yaml')
        with open(manifest_path, 'r') as f:
            payload = f.read()

        documents = list(yaml.safe_load_all(payload))
        documents[0]['schema'] = 'totally-invalid'
        invalid_payload = yaml.safe_dump_all(documents)

        resp = self.app.simulate_post('/api/v1.0/tests', body=invalid_payload)
        self.assertEqual(400, resp.status_code)

        m_helm = mock_Helm.return_value
        m_helm.__enter__.return_value = m_helm

        resp_body = json.loads(resp.text)
        self.assertEqual(400, resp_body['code'])
        self.assertEqual(1, resp_body['details']['errorCount'])
        self.assertIn(
            {
                'message': (
                    'An error occurred while building chart group: '
                    'Could not build ChartGroup named '
                    '"keystone-infra-services".'),
                'error': True,
                'kind': 'ValidationMessage',
                'level': 'Error',
                'name': 'ARM001',
                'documents': []
            }, resp_body['details']['messageList'])
        self.assertEqual(
            (
                'Failed to validate documents or generate Armada '
                'Manifest from documents.'), resp_body['message'])
        m_helm.__exit__.assert_called()

    @mock.patch('armada.utils.validate.Manifest')
    @mock.patch.object(api, 'Helm')
    def test_test_controller_manifest_failure_returns_400(
            self, mock_Helm, mock_manifest):
        rules = {'armada:test_manifest': '@'}
        self.policy.set_rules(rules)

        mock_manifest.return_value.get_manifest.side_effect = (
            manifest_exceptions.ManifestException(details='foo'))

        manifest_path = os.path.join(
            os.getcwd(), 'examples', 'keystone-manifest.yaml')
        with open(manifest_path, 'r') as f:
            payload = f.read()

        resp = self.app.simulate_post('/api/v1.0/tests', body=payload)
        self.assertEqual(400, resp.status_code)

        m_helm = mock_Helm.return_value
        m_helm.__enter__.return_value = m_helm

        resp_body = json.loads(resp.text)
        self.assertEqual(400, resp_body['code'])
        self.assertEqual(1, resp_body['details']['errorCount'])
        self.assertEqual(
            [
                {
                    'message': (
                        'An error occurred while generating the manifest: foo.'
                    ),
                    'error': True,
                    'kind': 'ValidationMessage',
                    'level': 'Error',
                    'name': 'ARM001',
                    'documents': []
                }
            ], resp_body['details']['messageList'])
        self.assertEqual(
            (
                'Failed to validate documents or generate Armada '
                'Manifest from documents.'), resp_body['message'])
        m_helm.__exit__.assert_called()


@test_utils.attr(type=['negative'])
class TestReleasesReleaseNameControllerNegativeTest(base.BaseControllerTest):
    @mock.patch.object(api, 'Helm')
    @mock.patch.object(test.Test, 'test_release_for_success')
    def test_test_controller_Helm_exc_returns_500(
            self, mock_test_release_for_success, mock_Helm):
        rules = {'armada:test_release': '@'}
        self.policy.set_rules(rules)

        mock_Helm.side_effect = Exception
        mock_test_release_for_success.side_effect = Exception

        namespace = 'fake-namespace'
        release = 'fake-release'
        resp = self.app.simulate_get(
            '/api/v1.0/test/{}/{}'.format(namespace, release))
        self.assertEqual(500, resp.status_code)


class TestReleasesReleaseNameControllerNegativeRbacTest(base.BaseControllerTest
                                                        ):
    @test_utils.attr(type=['negative'])
    def test_test_release_insufficient_permissions(self):
        """Tests the GET /api/v1.0/test/{namespace}/{release} endpoint returns 403
        following failed authorization.
        """
        rules = {'armada:test_release': policy_base.RULE_ADMIN_REQUIRED}
        self.policy.set_rules(rules)
        resp = self.app.simulate_get(
            '/api/v1.0/test/test-namespace/test-release')
        self.assertEqual(403, resp.status_code)


class TestReleasesManifestControllerNegativeRbacTest(base.BaseControllerTest):
    @test_utils.attr(type=['negative'])
    def test_test_manifest_insufficient_permissions(self):
        """Tests the POST /api/v1.0/tests endpoint returns 403 following failed
        authorization.
        """
        rules = {'armada:test_manifest': policy_base.RULE_ADMIN_REQUIRED}
        self.policy.set_rules(rules)
        resp = self.app.simulate_post('/api/v1.0/tests')
        self.assertEqual(403, resp.status_code)
