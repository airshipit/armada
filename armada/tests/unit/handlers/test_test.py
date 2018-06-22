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

from armada.handlers import tiller
from armada.handlers import test
from armada.tests.unit import base
from armada.tests.test_utils import AttrDict


class TestHandlerTestCase(base.ArmadaTestCase):

    def _test_test_release_for_success(self, expected_success, results):

        @mock.patch('armada.handlers.tiller.K8s')
        def do_test(_):
            tiller_obj = tiller.Tiller('host', '8080', None)
            release = 'release'

            tiller_obj.test_release = mock.Mock()
            tiller_obj.test_release.return_value = AttrDict(
                **{'results': results})
            success = test.test_release_for_success(tiller_obj, release)

            self.assertEqual(expected_success, success)

        do_test()

    def test_no_results(self):
        self._test_test_release_for_success(True, [])

    def test_unknown(self):
        self._test_test_release_for_success(False, [
            AttrDict(**{'status': test.TESTRUN_STATUS_SUCCESS}),
            AttrDict(**{'status': test.TESTRUN_STATUS_UNKNOWN})
        ])

    def test_success(self):
        self._test_test_release_for_success(
            True, [AttrDict(**{'status': test.TESTRUN_STATUS_SUCCESS})])

    def test_failure(self):
        self._test_test_release_for_success(False, [
            AttrDict(**{'status': test.TESTRUN_STATUS_SUCCESS}),
            AttrDict(**{'status': test.TESTRUN_STATUS_FAILURE})
        ])

    def test_running(self):
        self._test_test_release_for_success(False, [
            AttrDict(**{'status': test.TESTRUN_STATUS_SUCCESS}),
            AttrDict(**{'status': test.TESTRUN_STATUS_RUNNING})
        ])
