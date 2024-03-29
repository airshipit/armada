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

import mock
from oslo_config import cfg

from armada import api
from armada.api.controller import armada as armada_api
from armada.common.policies import base as policy_base
from armada.tests import test_utils
from armada.tests.unit.api import base

CONF = cfg.CONF


@mock.patch.object(
    armada_api.Apply, 'handle', armada_api.Apply.handle.__wrapped__)
class ArmadaControllerTest(base.BaseControllerTest):
    @mock.patch.object(api, 'Helm')
    @mock.patch.object(armada_api, 'Armada')
    @mock.patch.object(armada_api, 'ReferenceResolver')
    def test_armada_apply_resource(
            self, mock_resolver, mock_armada, mock_helm):
        """Tests the POST /api/v1.0/apply endpoint."""
        rules = {'armada:create_endpoints': '@'}
        self.policy.set_rules(rules)

        options = {
            'debug': 'true',
            'disable_update_pre': 'false',
            'disable_update_post': 'false',
            'enable_chart_cleanup': 'false',
            'skip_pre_flight': 'false',
            'wait': 'false',
            'timeout': '100'
        }

        m_helm = mock_helm.return_value
        m_helm.__enter__.return_value = m_helm

        expected_armada_options = {
            'disable_update_pre': False,
            'disable_update_post': False,
            'enable_chart_cleanup': False,
            'force_wait': False,
            'timeout': 100,
            'helm': m_helm,
            'target_manifest': None
        }

        payload_url = 'http://foo.com/test.yaml'
        payload = {'hrefs': [payload_url]}
        body = json.dumps(payload)
        expected = {'message': {'diff': [], 'install': [], 'upgrade': []}}

        mock_resolver.resolve_reference.return_value = \
            [b"---\nfoo: bar"]

        mock_armada.return_value.sync.return_value = \
            {'diff': [], 'install': [], 'upgrade': []}

        result = self.app.simulate_post(
            path='/api/v1.0/apply',
            body=body,
            headers={'Content-Type': 'application/json'},
            params=options)
        self.assertEqual(result.json, expected)
        self.assertEqual('application/json', result.headers['content-type'])

        mock_resolver.resolve_reference.assert_called_with([payload_url])
        mock_armada.assert_called_with(
            [{
                'foo': 'bar'
            }], **expected_armada_options)
        mock_armada.return_value.sync.assert_called()

        mock_helm.assert_called()
        m_helm.__exit__.assert_called()

    def test_armada_apply_no_href(self):
        """Tests /api/v1.0/apply returns 400 when hrefs list is empty."""
        rules = {'armada:create_endpoints': '@'}
        self.policy.set_rules(rules)

        options = {
            'debug': 'true',
            'disable_update_pre': 'false',
            'disable_update_post': 'false',
            'enable_chart_cleanup': 'false',
            'skip_pre_flight': 'false',
            'wait': 'false',
            'timeout': '100'
        }
        payload = {'hrefs': []}
        body = json.dumps(payload)

        result = self.app.simulate_post(
            path='/api/v1.0/apply',
            body=body,
            headers={'Content-Type': 'application/json'},
            params=options)
        self.assertEqual(result.status_code, 400)


class ArmadaControllerNegativeTest(base.BaseControllerTest):
    @test_utils.attr(type=['negative'])
    def test_armada_apply_raises_415_given_unsupported_media_type(self):
        """Tests the POST /api/v1.0/apply endpoint returns 415 given
        unsupported media type.
        """
        rules = {'armada:create_endpoints': '@'}
        self.policy.set_rules(rules)

        resp = self.app.simulate_post('/api/v1.0/apply', body=None)
        self.assertEqual(415, resp.status_code)


class ArmadaControllerNegativeRbacTest(base.BaseControllerTest):
    @test_utils.attr(type=['negative'])
    def test_armada_apply_resource_insufficient_permissions(self):
        """Tests the POST /api/v1.0/apply endpoint returns 403 following failed
        authorization.
        """
        rules = {'armada:create_endpoints': policy_base.RULE_ADMIN_REQUIRED}
        self.policy.set_rules(rules)
        resp = self.app.simulate_post('/api/v1.0/apply')
        self.assertEqual(403, resp.status_code)
