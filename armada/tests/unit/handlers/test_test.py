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
from armada.exceptions.helm_exceptions import HelmCommandException
from armada.handlers import helm
from armada.handlers import test
from armada.tests.unit import base


class TestHandlerTestCase(base.ArmadaTestCase):
    def _test_test_release_for_success(self, expected_success, exception):
        @mock.patch('armada.handlers.helm.K8s')
        def do_test(_):
            helm_obj = helm.Helm()
            release = 'release'

            helm_obj.test_release = mock.Mock()
            if exception:
                helm_obj.test_release.side_effect = exception

            test_handler = test.Test({}, release, helm_obj)
            success = test_handler.test_release_for_success()

            self.assertEqual(expected_success, success)

        do_test()

    def test_success(self):
        self._test_test_release_for_success(True, None)

    def test_failure(self):
        self._test_test_release_for_success(
            False, HelmCommandException(mock.Mock()))

    def test_exception(self):
        def test():
            self._test_test_release_for_success(False, Exception())

        self.assertRaises(Exception, test)

    def test_cg_disabled(self):
        """Test that tests are disabled when a chart group disables all
        tests.
        """
        test_handler = test.Test(
            chart={},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            cg_test_charts=False)

        assert test_handler.test_enabled is False

    def test_cg_disabled_test_key_enabled(self):
        """Test that tests are enabled when a chart group disables all
        tests and the deprecated, boolean `test` key is enabled.
        """
        test_handler = test.Test(
            chart={'test': True},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            cg_test_charts=False)

        assert test_handler.test_enabled is True

    def test_cg_disabled_test_values_enabled(self):
        """Test that tests are enabled when a chart group disables all
        tests and the `test.enabled` key is False.
        """
        test_handler = test.Test(
            chart={'test': {
                'enabled': True
            }},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            cg_test_charts=False)

        assert test_handler.test_enabled is True

    def test_cg_enabled_test_key_disabled(self):
        """Test that tests are disabled when a chart group enables all
        tests and the deprecated, boolean `test` key is disabled.
        """
        test_handler = test.Test(
            chart={'test': False},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            cg_test_charts=True)

        assert test_handler.test_enabled is False

    def test_cg_enabled_test_values_disabled(self):
        """Test that tests are disabled when a chart group enables all
        tests and the deprecated, boolean `test` key is disabled.
        """
        test_handler = test.Test(
            chart={'test': {
                'enabled': False
            }},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            cg_test_charts=True)

        assert test_handler.test_enabled is False

    def test_enable_all_cg_disabled(self):
        """Test that tests are enabled when the `enable_all` parameter is
        True and the chart group `test_enabled` key is disabled.
        """
        test_handler = test.Test(
            chart={},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            cg_test_charts=False,
            enable_all=True)

        assert test_handler.test_enabled is True

    def test_enable_all_test_key_disabled(self):
        """Test that tests are enabled when the `enable_all` parameter is
        True and the deprecated, boolean `test` key is disabled.
        """
        test_handler = test.Test(
            chart={'test': True},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            enable_all=True)

        assert test_handler.test_enabled is True

    def test_enable_all_test_values_disabled(self):
        """Test that tests are enabled when the `enable_all` parameter is
        True and the `test.enabled` key is False.
        """
        test_handler = test.Test(
            chart={'test': {
                'enabled': False
            }},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock(),
            enable_all=True)

        assert test_handler.test_enabled is True

    def test_deprecated_test_key_false(self):
        """Test that tests can be disabled using the deprecated, boolean value
        for a chart's test key.
        """
        test_handler = test.Test(
            chart={'test': False},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock())

        assert not test_handler.test_enabled

    def test_deprecated_test_key_timeout(self):
        """Test that the default helm timeout is used when tests are enabled
        using the deprecated, boolean value for a chart's `test` key.
        """
        mock_helm = mock.Mock()
        test_handler = test.Test(
            chart={'test': True},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock_helm)

        assert test_handler.timeout == const.DEFAULT_TEST_TIMEOUT

    def test_tests_disabled(self):
        """Test that tests are disabled by a chart's values using the
        `test.enabled` path.
        """
        test_handler = test.Test(
            chart={'test': {
                'enabled': False
            }},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock())

        assert test_handler.test_enabled is False

    def test_no_test_values(self):
        """Test that the default values are enforced when no chart `test`
        values are provided (i.e. tests are enabled).
        """
        test_handler = test.Test(
            chart={},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock())

        assert test_handler.test_enabled is True

    def test_default_timeout_value(self):
        """Test that the default timeout value is used if a test timeout value,
        `test.timeout` is not provided.
        """
        test_handler = test.Test(
            chart={'test': {
                'enabled': True
            }},
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock())

        assert test_handler.timeout == helm.DEFAULT_HELM_TIMEOUT

    def test_timeout_value(self):
        """Test that a chart's test timeout value, `test.timeout` overrides the
        default test timeout.
        """
        chart = {'test': {'enabled': True, 'timeout': 800}}

        test_handler = test.Test(
            chart=chart,
            release_id=helm.HelmReleaseId('release_ns', 'release'),
            helm=mock.Mock())

        assert test_handler.timeout is chart['test']['timeout']
