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


class ReleasesControllerTest(base.BaseControllerTest):
    @mock.patch.object(api, 'Helm')
    def test_helm_releases(self, mock_helm):
        """Tests GET /api/v1.0/releases endpoint."""
        rules = {'armada:get_release': '@'}
        self.policy.set_rules(rules)

        def _get_fake_release(name, namespace):
            fake_release = mock.Mock(namespace='%s_namespace' % namespace)
            fake_release.configure_mock(name=name)
            return fake_release

        m_helm = mock_helm.return_value
        m_helm.__enter__.return_value = m_helm
        m_helm.list_release_ids.return_value = [
            _get_fake_release('foo', 'bar'),
            _get_fake_release('baz', 'qux')
        ]

        result = self.app.simulate_get('/api/v1.0/releases')
        expected = {
            'releases': {
                'bar_namespace': ['foo'],
                'qux_namespace': ['baz']
            }
        }

        self.assertEqual(expected, result.json)
        mock_helm.assert_called_once()
        m_helm.list_release_ids.assert_called_once_with()
        m_helm.__exit__.assert_called()

    @mock.patch.object(api, 'Helm')
    def test_helm_releases_with_params(self, mock_helm):
        """Tests GET /api/v1.0/releases endpoint with query parameters."""
        rules = {'armada:get_release': '@'}
        self.policy.set_rules(rules)

        def _get_fake_release(name, namespace):
            fake_release = mock.Mock(namespace='%s_namespace' % namespace)
            fake_release.configure_mock(name=name)
            return fake_release

        m_helm = mock_helm.return_value
        m_helm.__enter__.return_value = m_helm
        m_helm.list_release_ids.return_value = [
            _get_fake_release('foo', 'bar'),
            _get_fake_release('baz', 'qux')
        ]

        result = self.app.simulate_get(
            '/api/v1.0/releases', params_csv=False, params={})
        expected = {
            'releases': {
                'bar_namespace': ['foo'],
                'qux_namespace': ['baz']
            }
        }

        self.assertEqual(expected, result.json)
        mock_helm.assert_called_once()
        m_helm.list_release_ids.assert_called_once_with()
        m_helm.__exit__.assert_called()


class ReleasesControllerNegativeRbacTest(base.BaseControllerTest):
    @test_utils.attr(type=['negative'])
    def test_list_helm_releases_insufficient_permissions(self):
        """Tests the GET /api/v1.0/releases endpoint returns 403 following
        failed authorization.
        """
        rules = {'armada:get_release': policy_base.RULE_ADMIN_REQUIRED}
        self.policy.set_rules(rules)
        resp = self.app.simulate_get('/api/v1.0/releases')
        self.assertEqual(403, resp.status_code)
