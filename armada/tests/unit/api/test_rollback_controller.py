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

from armada.api.controller import rollback
from armada.common.policies import base as policy_base
from armada.tests import test_utils
from armada.tests.unit.api import base


class RollbackReleaseControllerTest(base.BaseControllerTest):

    @mock.patch.object(rollback, 'Tiller')
    def test_rollback_controller_pass(self, mock_tiller):
        rules = {'armada:rollback_release': '@'}
        self.policy.set_rules(rules)

        rollback_release = mock_tiller.return_value.rollback_release
        rollback_release.return_value = None

        tiller_host = 'host'
        tiller_port = '8080'
        tiller_namespace = 'tn'
        release = 'test-release'
        version = '2'
        dry_run = 'false'
        wait = 'true'
        timeout = '123'
        force = 'true'
        recreate_pods = 'true'

        resp = self.app.simulate_post(
            '/api/v1.0/rollback/{}'.format(release),
            params={
                'tiller_host': tiller_host,
                'tiller_port': tiller_port,
                'tiller_namespace': tiller_namespace,
                'dry_run': dry_run,
                'version': version,
                'wait': wait,
                'timeout': timeout,
                'force': force,
                'recreate_pods': recreate_pods
            })

        mock_tiller.assert_called_once_with(
            tiller_host=tiller_host,
            tiller_port=8080,
            tiller_namespace=tiller_namespace,
            dry_run=False)

        rollback_release.assert_called_once_with(
            release, 2, wait=True, timeout=123, force=True, recreate_pods=True)

        self.assertEqual(200, resp.status_code)
        self.assertEqual('Rollback of test-release complete.',
                         json.loads(resp.text)['message'])


@test_utils.attr(type=['negative'])
class RollbackReleaseControllerNegativeTest(base.BaseControllerTest):

    @mock.patch.object(rollback, 'Tiller')
    def test_rollback_controller_tiller_exc_return_500(self, mock_tiller):
        rules = {'armada:rollback_release': '@'}
        self.policy.set_rules(rules)

        mock_tiller.side_effect = Exception

        resp = self.app.simulate_post('/api/v1.0/rollback/fake-release')
        self.assertEqual(500, resp.status_code)


@test_utils.attr(type=['negative'])
class RollbackReleaseControllerNegativeRbacTest(base.BaseControllerTest):

    def test_rollback_release_insufficient_permissions(self):
        """Tests the GET /api/v1.0/rollback/{release} endpoint returns 403
        following failed authorization.
        """
        rules = {'armada:rollback_release': policy_base.RULE_ADMIN_REQUIRED}
        self.policy.set_rules(rules)
        resp = self.app.simulate_post('/api/v1.0/rollback/fake-release')
        self.assertEqual(403, resp.status_code)
