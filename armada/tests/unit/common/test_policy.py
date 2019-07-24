#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
from oslo_policy import policy as common_policy
import testtools

from armada.common import policy
from armada import conf as cfg
from armada.exceptions import base_exception as exc
from armada.tests.unit import fixtures

CONF = cfg.CONF


class PolicyTestCase(testtools.TestCase):
    def setUp(self):
        super(PolicyTestCase, self).setUp()
        self.rules = {
            "true": [],
            "armada:validate_manifest": [],
            "armada:create_endpoints": [["false:false"]]
        }
        self.useFixture(fixtures.RealPolicyFixture(False))
        self._set_rules()
        self.credentials = {}
        self.target = {}

    def _set_rules(self):
        curr_rules = common_policy.Rules.from_dict(self.rules)
        policy._ENFORCER.set_rules(curr_rules)

    @mock.patch.object(policy, 'LOG', autospec=True)
    @mock.patch('armada.api.ArmadaRequestContext', autospec=True)
    def test_enforce_nonexistent_action(self, mock_ctx, mock_log):
        """Validates that unregistered default policy throws exception."""
        action = "example:nope"
        mock_ctx.to_policy_view.return_value = self.credentials

        self.assertRaises(
            exc.ActionForbidden, policy._enforce_policy, action, self.target,
            mock_ctx)
        mock_log.exception.assert_called_once_with(
            'Policy not registered for %(action)s', {'action': 'example:nope'})

    @mock.patch('armada.api.ArmadaRequestContext', autospec=True)
    def test_enforce_allowed_action(self, mock_ctx):
        """Validates that allowed policy action can be performed."""
        action = "armada:validate_manifest"
        mock_ctx.to_policy_view.return_value = self.credentials

        policy._enforce_policy(action, self.target, mock_ctx)

    @mock.patch('armada.api.ArmadaRequestContext', autospec=True)
    def test_enforce_disallowed_action(self, mock_ctx):
        """Validates that disallowed policy action cannot be performed."""
        action = "armada:create_endpoints"
        mock_ctx.to_policy_view.return_value = self.credentials

        self.assertRaises(
            exc.ActionForbidden, policy._enforce_policy, action, self.target,
            mock_ctx)
