# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
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

import os

import mock
import yaml

from armada import const
from armada.handlers import armada
from armada.tests.unit import base
from armada.handlers import helm
from armada.utils.release import release_prefixer, get_release_status
from armada.exceptions import ManifestException
from armada.exceptions.override_exceptions import InvalidOverrideValueException
from armada.exceptions.validate_exceptions import InvalidManifestException
from armada.exceptions.armada_exceptions import ChartDeployException

TEST_YAML = """
---
schema: armada/Manifest/v1
metadata:
  schema: metadata/Document/v1
  name: example-manifest
data:
  release_prefix: armada
  chart_groups:
    - example-group
---
schema: armada/ChartGroup/v1
metadata:
  schema: metadata/Document/v1
  name: example-group
data:
  description: this is a test
  sequenced: True
  chart_group:
    - example-chart-1
    - example-chart-2
    - example-chart-3
    - example-chart-4
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: example-chart-4
data:
    chart_name: test_chart_4
    release: test_chart_4
    namespace: test
    values: {}
    source:
      type: local
      location: /tmp/dummy/armada
      subpath: chart_4
    dependencies: []
    test: true
    wait:
      timeout: 10
    upgrade:
      no_hooks: false
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: example-chart-3
data:
    chart_name: test_chart_3
    release: test_chart_3
    namespace: test
    values: {}
    source:
      type: local
      location: /tmp/dummy/armada
      subpath: chart_3
    dependencies: []
    protected:
      continue_processing: false
    wait:
      timeout: 10
    upgrade:
      no_hooks: false
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: example-chart-2
data:
    chart_name: test_chart_2
    release: test_chart_2
    namespace: test
    values: {}
    source:
      type: local
      location: /tmp/dummy/armada
      subpath: chart_2
    dependencies: []
    protected:
      continue_processing: true
    wait:
      timeout: 10
    upgrade:
      no_hooks: false
      options:
        force: true
    test:
      enabled: true
---
schema: armada/Chart/v1
metadata:
  schema: metadata/Document/v1
  name: example-chart-1
data:
    chart_name: test_chart_1
    release: test_chart_1
    namespace: test
    values: {}
    source:
      type: git
      location: git://opendev.org/dummy/armada.git
      subpath: chart_1
      reference: master
    dependencies: []
    wait:
      timeout: 10
      native:
        enabled: true
    test:
      enabled: true
"""

CHART_SOURCES = (
    ('git://opendev.org/dummy/armada.git',
     'chart_1'), ('/tmp/dummy/armada', 'chart_2'),
    ('/tmp/dummy/armada', 'chart_3'), ('/tmp/dummy/armada', 'chart_4'))


# TODO(seaneagan): Add unit tests with dependencies, including transitive.
def set_source_dir(ch, manifest=None):
    d = ch['data']
    d['source_dir'] = (d['source']['location'], d['source']['subpath'])


class ArmadaHandlerTestCase(base.ArmadaTestCase):
    def _test_pre_flight_ops(self, armada_obj, MockChartDownload):
        MockChartDownload.return_value.get_chart.side_effect = set_source_dir
        armada_obj.pre_flight_ops()

        expected_config = {
            'schema': 'armada/Manifest/v1',
            'metadata': {
                'schema': 'metadata/Document/v1',
                'name': 'example-manifest'
            },
            'data': {
                'release_prefix': 'armada',
                'chart_groups': [{
                    'schema': 'armada/ChartGroup/v1',
                    'metadata': {
                        'schema': 'metadata/Document/v1',
                        'name': 'example-group'
                    },
                    'data': {
                        'chart_group': [{
                            'schema': 'armada/Chart/v1',
                            'metadata': {
                                'schema': 'metadata/Document/v1',
                                'name': 'example-chart-1'
                            },
                            'data': {
                                'dependencies': [],
                                'chart_name': 'test_chart_1',
                                'namespace': 'test',
                                'release': 'test_chart_1',
                                'source': {
                                    'location':
                                        'git://opendev.org/dummy/armada.git',
                                    'reference': 'master',
                                    'subpath': 'chart_1',
                                    'type': 'git'
                                },
                                'source_dir': CHART_SOURCES[0],
                                'values': {},
                                'wait': {
                                    'timeout': 10,
                                    'native': {
                                        'enabled': True
                                    }
                                },
                                'test': {
                                    'enabled': True
                                }
                            }
                        }, {
                            'schema': 'armada/Chart/v1',
                            'metadata': {
                                'schema': 'metadata/Document/v1',
                                'name': 'example-chart-2'
                            },
                            'data': {
                                'dependencies': [],
                                'chart_name': 'test_chart_2',
                                'namespace': 'test',
                                'protected': {
                                    'continue_processing': True
                                },
                                'release': 'test_chart_2',
                                'source': {
                                    'location': '/tmp/dummy/armada',
                                    'subpath': 'chart_2',
                                    'type': 'local'
                                },
                                'source_dir': CHART_SOURCES[1],
                                'values': {},
                                'wait': {
                                    'timeout': 10
                                },
                                'upgrade': {
                                    'no_hooks': False,
                                    'options': {
                                        'force': True
                                    }
                                },
                                'test': {
                                    'enabled': True
                                }
                            }
                        }, {
                            'schema': 'armada/Chart/v1',
                            'metadata': {
                                'schema': 'metadata/Document/v1',
                                'name': 'example-chart-3'
                            },
                            'data': {
                                'dependencies': [],
                                'chart_name': 'test_chart_3',
                                'namespace': 'test',
                                'protected': {
                                    'continue_processing': False
                                },
                                'release': 'test_chart_3',
                                'source': {
                                    'location': '/tmp/dummy/armada',
                                    'subpath': 'chart_3',
                                    'type': 'local'
                                },
                                'source_dir': CHART_SOURCES[2],
                                'values': {},
                                'wait': {
                                    'timeout': 10
                                },
                                'upgrade': {
                                    'no_hooks': False
                                }
                            }
                        }, {
                            'schema': 'armada/Chart/v1',
                            'metadata': {
                                'schema': 'metadata/Document/v1',
                                'name': 'example-chart-4'
                            },
                            'data': {
                                'dependencies': [],
                                'chart_name': 'test_chart_4',
                                'namespace': 'test',
                                'release': 'test_chart_4',
                                'source': {
                                    'location': '/tmp/dummy/armada',
                                    'subpath': 'chart_4',
                                    'type': 'local'
                                },
                                'source_dir': CHART_SOURCES[3],
                                'values': {},
                                'wait': {
                                    'timeout': 10
                                },
                                'upgrade': {
                                    'no_hooks': False
                                },
                                'test': True
                            }
                        }],
                        'description': 'this is a test',
                        'sequenced': True
                    }
                }]
            }
        }  # yapf: disable

        self.assertTrue(hasattr(armada_obj, 'manifest'))
        self.assertIsInstance(armada_obj.manifest, dict)
        self.assertIn('data', armada_obj.manifest)
        self.assertEqual(expected_config, armada_obj.manifest)

    @mock.patch.object(armada, 'ChartDownload')
    def test_pre_flight_ops(self, MockChartDownload):
        """Test pre-flight checks and operations."""
        yaml_documents = list(yaml.safe_load_all(TEST_YAML))
        m_helm = mock.Mock()
        armada_obj = armada.Armada(yaml_documents, m_helm)

        self._test_pre_flight_ops(armada_obj, MockChartDownload)

        MockChartDownload.return_value.get_chart.assert_called()

    @mock.patch.object(armada, 'ChartDownload')
    def test_post_flight_ops(self, MockChartDownload):
        """Test post-flight operations."""
        yaml_documents = list(yaml.safe_load_all(TEST_YAML))

        # Mock methods called by `pre_flight_ops()`.
        m_helm = mock.Mock()

        armada_obj = armada.Armada(yaml_documents, m_helm)

        self._test_pre_flight_ops(armada_obj, MockChartDownload)

        armada_obj.post_flight_ops()

        for group in armada_obj.manifest['data']['chart_groups']:
            for counter, chart in enumerate(group.get(const.KEYWORD_DATA).get(
                    const.KEYWORD_CHARTS)):
                if chart.get(
                        const.KEYWORD_DATA).get('source').get('type') == 'git':
                    MockChartDownload.return_value.cleanup.assert_called_with()

    # TODO(seaneagan): Separate ChartDeploy tests into separate module.
    # TODO(seaneagan): Once able to make mock library sufficiently thread safe,
    # run sync tests for unsequenced as well by moving them to separate test
    # class with two separate subclasses which set chart group `sequenced`
    # field, one to true, one to false.
    def _test_sync(
            self,
            known_releases,
            test_success=True,
            test_failure_to_run=False,
            expected_last_test_result=None,
            diff={'some_key': {'some diff'}}):
        """Test install functionality from the sync() method."""

        @mock.patch.object(armada.Armada, 'post_flight_ops')
        @mock.patch.object(armada, 'ChartDownload')
        @mock.patch('armada.handlers.chart_deploy.ChartBuilder.from_chart_doc')
        @mock.patch('armada.handlers.chart_deploy.Test')
        def _do_test(
                mock_test, mock_chartbuilder, MockChartDownload,
                mock_post_flight):
            MockChartDownload.return_value.get_chart.side_effect = \
                set_source_dir
            # Instantiate Armada object.
            yaml_documents = list(yaml.safe_load_all(TEST_YAML))
            m_helm = mock.MagicMock()
            armada_obj = armada.Armada(yaml_documents, m_helm)
            prefix = armada_obj.manifest['data']['release_prefix']

            def release_metadata(release_id, **kwargs):
                try:
                    return next(
                        r for r in known_releases
                        if release_id.name == r['name']
                        and release_id.namespace == r['namespace'])
                except StopIteration:
                    return None

            m_helm.release_metadata.side_effect = release_metadata
            armada_obj.chart_deploy.get_diff = mock.Mock()

            cg = armada_obj.manifest['data']['chart_groups'][0]
            chart_group = cg['data']
            charts = chart_group['chart_group']
            cg_test_all_charts = chart_group.get('test_charts')

            mock_test_release = mock_test.return_value.test_release
            if test_failure_to_run:
                mock_test_release.side_effect = Exception('test failed to run')
            else:
                if not test_success:
                    mock_test_release.side_effect = Exception('test failed')
            mock_test.return_value.timeout = const.DEFAULT_TEST_TIMEOUT

            # Stub out irrelevant methods called by `armada.sync()`.
            mock_chartbuilder.get_helm_chart.return_value = None

            # Simulate chart diff, upgrade should only happen if non-empty.
            armada_obj.chart_deploy.get_diff.return_value = diff

            armada_obj.sync()

            expected_install_release_calls = []
            expected_upgrade_release_calls = []
            expected_uninstall_release_calls = []
            expected_test_constructor_calls = []

            for c in charts:
                chart = c['data']
                release = chart['release']
                release_name = release_prefixer(prefix, release)
                release_id = helm.HelmReleaseId(
                    chart['namespace'], release_name)
                source_dir = chart['source_dir']
                source_directory = os.path.join(*source_dir)

                # Simplified check because the actual code uses logical-or's
                # multiple conditions, so this is enough.
                native_wait_enabled = (
                    chart['wait'].get('native', {}).get('enabled', True))

                if release_name not in [x['name'] for x in known_releases]:
                    expected_install_release_calls.append(
                        mock.call(
                            source_directory,
                            release_id,
                            values=chart['values'],
                            wait=native_wait_enabled,
                            timeout=mock.ANY))
                else:
                    target_release = None
                    for known_release in known_releases:
                        if known_release['name'] == release_name:
                            target_release = known_release
                            break
                    if target_release:
                        status = get_release_status(target_release)
                        if status == helm.STATUS_FAILED:
                            protected = chart.get('protected', {})
                            if not protected:
                                expected_uninstall_release_calls.append(
                                    mock.call(
                                        release_id,
                                        purge=True,
                                        timeout=const.DEFAULT_DELETE_TIMEOUT))
                                expected_install_release_calls.append(
                                    mock.call(
                                        source_directory,
                                        release_id,
                                        values=chart['values'],
                                        wait=native_wait_enabled,
                                        timeout=mock.ANY))
                            else:
                                p_continue = protected.get(
                                    'continue_processing', False)
                                if p_continue:
                                    continue
                                else:
                                    if chart_group['sequenced']:
                                        break

                        if status == helm.STATUS_DEPLOYED:
                            if diff:
                                upgrade = chart.get('upgrade', {})
                                disable_hooks = upgrade.get('no_hooks', False)
                                options = upgrade.get('options', {})
                                force = options.get('force', False)

                                expected_upgrade_release_calls.append(
                                    mock.call(
                                        source_directory,
                                        release_id,
                                        disable_hooks=disable_hooks,
                                        force=force,
                                        values=chart['values'],
                                        wait=native_wait_enabled,
                                        timeout=mock.ANY))

                expected_test_constructor_calls.append(
                    mock.call(
                        chart,
                        release_id,
                        m_helm,
                        cg_test_charts=cg_test_all_charts))

            any_order = not chart_group['sequenced']
            # Verify that at least 1 release is either installed or updated.
            self.assertTrue(
                len(expected_install_release_calls) >= 1
                or len(expected_upgrade_release_calls) >= 1)
            # Verify that the expected number of non-deployed releases are
            # installed with expected arguments.
            self.assertEqual(
                len(expected_install_release_calls),
                m_helm.install_release.call_count)
            m_helm.install_release.assert_has_calls(
                expected_install_release_calls, any_order=any_order)
            # Verify that the expected number of deployed releases are
            # updated with expected arguments.
            self.assertEqual(
                len(expected_upgrade_release_calls),
                m_helm.upgrade_release.call_count)
            m_helm.upgrade_release.assert_has_calls(
                expected_upgrade_release_calls, any_order=any_order)
            # Verify that the expected number of deployed releases are
            # uninstalled with expected arguments.
            self.assertEqual(
                len(expected_uninstall_release_calls),
                m_helm.uninstall_release.call_count)
            m_helm.uninstall_release.assert_has_calls(
                expected_uninstall_release_calls, any_order=any_order)
            # Verify that the expected number of deployed releases are
            # tested with expected arguments.
            self.assertEqual(
                len(expected_test_constructor_calls), mock_test.call_count)

            mock_test.assert_has_calls(
                expected_test_constructor_calls, any_order=True)

        _do_test()

    def _get_chart_by_name(self, name):
        name = name.split('armada-')[-1]
        yaml_documents = list(yaml.safe_load_all(TEST_YAML))
        return [
            c for c in yaml_documents if c['data'].get('chart_name') == name
        ][0]

    def get_mock_release(self, name, status, last_test_results=[]):
        chart = self._get_chart_by_name(name)

        def get_test_hook(index, success):
            return {
                "kind": "Pod",
                "events": ["test"],
                "last_run": {
                    "phase": ""
                }
            }

        hooks = [get_test_hook(i, r) for i, r in enumerate(last_test_results)]

        return {
            "name": name,
            "namespace": "test",
            "version": 1,
            "chart": chart,
            "config": {},
            "info": {
                "status": status
            },
            "hooks": hooks
        }

    def test_armada_sync_with_no_deployed_releases(self):
        known_releases = []
        self._test_sync(known_releases)

    def test_armada_sync_with_one_deployed_release(self):
        c1 = 'armada-test_chart_1'

        known_releases = [self.get_mock_release(c1, helm.STATUS_DEPLOYED)]
        self._test_sync(known_releases)

    def test_armada_sync_with_one_deployed_release_no_diff(self):
        c1 = 'armada-test_chart_1'

        known_releases = [self.get_mock_release(c1, helm.STATUS_DEPLOYED)]
        self._test_sync(known_releases, diff=set())

    def test_armada_sync_with_failed_test_result(self):
        c1 = 'armada-test_chart_1'

        known_releases = [
            self.get_mock_release(
                c1, helm.STATUS_DEPLOYED, last_test_results=[False])
        ]
        self._test_sync(
            known_releases, diff=set(), expected_last_test_result=False)

    def test_armada_sync_with_success_test_result(self):
        c1 = 'armada-test_chart_1'

        known_releases = [
            self.get_mock_release(
                c1, helm.STATUS_DEPLOYED, last_test_results=[True])
        ]
        self._test_sync(
            known_releases, diff=set(), expected_last_test_result=True)

    def test_armada_sync_with_success_test_result_no_tests(self):
        c1 = 'armada-test_chart_1'

        known_releases = [
            self.get_mock_release(
                c1, helm.STATUS_DEPLOYED, last_test_results=[])
        ]
        self._test_sync(
            known_releases, diff=set(), expected_last_test_result=True)

    def test_armada_sync_with_both_deployed_releases(self):
        c1 = 'armada-test_chart_1'
        c2 = 'armada-test_chart_2'

        known_releases = [
            self.get_mock_release(c1, helm.STATUS_DEPLOYED),
            self.get_mock_release(c2, helm.STATUS_DEPLOYED)
        ]
        self._test_sync(known_releases)

    def test_armada_sync_with_unprotected_releases(self):
        c1 = 'armada-test_chart_1'

        known_releases = [self.get_mock_release(c1, helm.STATUS_FAILED)]
        self._test_sync(known_releases)

    def test_armada_sync_with_protected_releases_continue(self):
        c1 = 'armada-test_chart_1'
        c2 = 'armada-test_chart_2'

        known_releases = [
            self.get_mock_release(c2, helm.STATUS_FAILED),
            self.get_mock_release(c1, helm.STATUS_FAILED)
        ]
        self._test_sync(known_releases)

    def test_armada_sync_with_protected_releases_halt(self):
        c3 = 'armada-test_chart_3'

        known_releases = [self.get_mock_release(c3, helm.STATUS_FAILED)]

        def _test_method():
            self._test_sync(known_releases)

        self.assertRaises(ChartDeployException, _test_method)

    def test_armada_sync_test_failure(self):
        def _test_method():
            self._test_sync([], test_success=False)

        self.assertRaises(ChartDeployException, _test_method)

    def test_armada_sync_test_failure_to_run(self):
        def _test_method():
            self._test_sync([], test_failure_to_run=True)

        self.assertRaises(ChartDeployException, _test_method)


class ArmadaNegativeHandlerTestCase(base.ArmadaTestCase):
    @mock.patch.object(armada, 'ChartDownload')
    def test_armada_get_manifest_exception(self, MockChartDownload):
        """Test armada handling with invalid manifest."""
        yaml_documents = list(yaml.safe_load_all(TEST_YAML))
        error_re = ('.*Documents must include at least one of each of .*')
        self.assertRaisesRegexp(
            ManifestException, error_re, armada.Armada, yaml_documents[:1],
            mock.MagicMock())

    @mock.patch.object(armada, 'ChartDownload')
    def test_armada_override_exception(self, MockChartDownload):
        """Test Armada checks with invalid chart override."""
        yaml_documents = list(yaml.safe_load_all(TEST_YAML))
        override = ('chart:example-chart-2:name=' 'overridden', )

        error_re = ('is not a valid override statement')
        with self.assertRaisesRegexp(InvalidOverrideValueException, error_re):
            armada.Armada(yaml_documents, mock.MagicMock(), set_ovr=override)

    @mock.patch.object(armada, 'ChartDownload')
    def test_armada_manifest_exception_override_none(self, MockChartDownload):
        """Test Armada checks with invalid manifest."""
        yaml_documents = list(yaml.safe_load_all(TEST_YAML))
        example_document = [
            d for d in yaml_documents
            if d['metadata']['name'] == 'example-chart-4'
        ][0]
        del example_document['data']['release']

        error_re = ('Invalid document .*')
        with self.assertRaisesRegexp(InvalidManifestException, error_re):
            armada.Armada(yaml_documents, mock.MagicMock(), set_ovr=None)
