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

import mock
from oslo_config import cfg

from armada import api
from armada.common.policies import base as policy_base
from armada.tests import test_utils
from armada.tests.unit.api import base

CONF = cfg.CONF


class TillerControllerTest(base.BaseControllerTest):
    @mock.patch.object(api, 'Tiller')
    def test_get_tiller_status(self, mock_tiller):
        """Tests GET /api/v1.0/status endpoint."""
        rules = {'tiller:get_status': '@'}
        self.policy.set_rules(rules)

        m_tiller = mock_tiller.return_value
        m_tiller.__enter__.return_value = m_tiller
        m_tiller.tiller_status.return_value = 'fake_status'
        m_tiller.tiller_version.return_value = 'fake_version'

        result = self.app.simulate_get('/api/v1.0/status')
        expected = {
            'tiller': {
                'version': 'fake_version',
                'state': 'fake_status'
            }
        }

        self.assertEqual(expected, result.json)
        self.assertEqual('application/json', result.headers['content-type'])
        mock_tiller.assert_called_once()
        m_tiller.__exit__.assert_called()

    @mock.patch.object(api, 'Tiller')
    def test_get_tiller_status_with_params(self, mock_tiller):
        """Tests GET /api/v1.0/status endpoint with query parameters."""
        rules = {'tiller:get_status': '@'}
        self.policy.set_rules(rules)

        m_tiller = mock_tiller.return_value
        m_tiller.__enter__.return_value = m_tiller
        m_tiller.tiller_status.return_value = 'fake_status'
        m_tiller.tiller_version.return_value = 'fake_version'

        result = self.app.simulate_get(
            '/api/v1.0/status', params_csv=False, params={})
        expected = {
            'tiller': {
                'version': 'fake_version',
                'state': 'fake_status'
            }
        }

        self.assertEqual(expected, result.json)
        self.assertEqual('application/json', result.headers['content-type'])
        mock_tiller.assert_called_once()
        m_tiller.__exit__.assert_called()


class TillerControllerNegativeRbacTest(base.BaseControllerTest):
    @test_utils.attr(type=['negative'])
    def test_get_tiller_status_insufficient_permissions(self):
        """Tests the GET /api/v1.0/status endpoint returns 403 following
        failed authorization.
        """
        rules = {'tiller:get_status': policy_base.RULE_ADMIN_REQUIRED}
        self.policy.set_rules(rules)
        resp = self.app.simulate_get('/api/v1.0/status')
        self.assertEqual(403, resp.status_code)
