# Copyright 2017 The Armada Authors.
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
from pathlib import Path
import shutil

import fixtures
import mock
import testtools
import yaml

from armada import const
from armada.handlers.chartbuilder import ChartBuilder
from armada.exceptions import chartbuilder_exceptions


class BaseChartBuilderTestCase(testtools.TestCase):
    chart_yaml = """
        apiVersion: v1
        description: A sample Helm chart for Kubernetes
        name: hello-world-chart
        version: 0.1.0
    """

    chart_doc_yaml = """
        schema: armada/Chart/v1
        metadata:
            name: test
        data:
            chart_name: mariadb
            release: mariadb
            namespace: openstack
            install:
                no_hooks: false
            upgrade:
                no_hooks: false
            values:
                replicas: 1
                volume:
                    size: 1Gi
            source:
                type: git
                location: git://opendev.org/openstack/openstack-helm
                subpath: mariadb
                reference: master
            dependencies: []
    """

    dep_chart_yaml = """
        apiVersion: v1
        description: Another sample Helm chart for Kubernetes
        name: dependency-chart
        version: 0.1.0
    """

    dep_chart_doc_yaml = """
        schema: armada/Chart/v1
        metadata:
            name: dep
        data:
            chart_name: keystone
            release: keystone
            namespace: undercloud
            timeout: 100
            install:
                no_hooks: false
            upgrade:
                no_hooks: false
            values: {}
            source:
                type: git
                location: git://github.com/example/example
                subpath: example-chart
                reference: master
            dependencies: []
    """

    def _write_temporary_file_contents(self, directory, filename, contents):
        path = os.path.join(directory, filename)
        fd = os.open(path, os.O_CREAT | os.O_WRONLY)
        try:
            os.write(fd, contents.encode('utf-8'))
        finally:
            os.close(fd)

    def _get_test_chart(self, chart_dir):
        return {
            'schema': 'armada/Chart/v1',
            'metadata': {
                'name': 'test'
            },
            const.KEYWORD_DATA: {
                'source_dir': (chart_dir, '')
            }
        }


class ChartBuilderTestCase(BaseChartBuilderTestCase):
    def test_get_helm_chart_success(self):
        chart_dir = self.useFixture(fixtures.TempDir())
        self.addCleanup(shutil.rmtree, chart_dir.path)
        helm_mock = mock.Mock()
        helm_mock.upgrade_release.return_value = {"chart": mock.sentinel.chart}
        chartbuilder = ChartBuilder.from_chart_doc(
            self._get_test_chart(chart_dir.path), helm_mock)
        release_id = mock.Mock()
        values = mock.Mock()
        actual_chart = chartbuilder.get_helm_chart(release_id, values)
        self.assertIs(mock.sentinel.chart, actual_chart)

    def test_get_helm_chart_fail(self):
        chart_dir = self.useFixture(fixtures.TempDir())
        self.addCleanup(shutil.rmtree, chart_dir.path)
        helm_mock = mock.Mock()
        helm_mock.upgrade_release.side_effect = Exception()
        chartbuilder = ChartBuilder.from_chart_doc(
            self._get_test_chart(chart_dir.path), helm_mock)

        def test():
            release_id = mock.Mock()
            values = mock.Mock()
            chartbuilder.get_helm_chart(release_id, values)

        self.assertRaises(
            chartbuilder_exceptions.HelmChartBuildException, test)

    def test_dependency_resolution(self):
        # Main chart directory and files.
        chart_dir = self.useFixture(fixtures.TempDir())
        self.addCleanup(shutil.rmtree, chart_dir.path)
        self._write_temporary_file_contents(
            chart_dir.path, 'Chart.yaml', self.chart_yaml)
        chart_doc = yaml.safe_load(self.chart_doc_yaml)
        chart_doc['data']['source_dir'] = (chart_dir.path, '')

        # Dependency chart directory and files.
        dep_chart_dir = self.useFixture(fixtures.TempDir())
        self.addCleanup(shutil.rmtree, dep_chart_dir.path)
        self._write_temporary_file_contents(
            dep_chart_dir.path, 'Chart.yaml', self.dep_chart_yaml)
        dep_chart_doc = yaml.safe_load(self.dep_chart_doc_yaml)
        dep_chart_doc['data']['source_dir'] = (dep_chart_dir.path, '')

        # Add dependency
        chart_doc['data']['dependencies'] = [dep_chart_doc]

        # Mock helm cli call
        helm_mock = mock.Mock()
        helm_mock.show_chart.return_value = yaml.safe_load(self.dep_chart_yaml)
        ChartBuilder.from_chart_doc(chart_doc, helm_mock)

        expected_symlink_path = Path(
            chart_dir.path).joinpath('charts').joinpath('dependency-chart')
        self.assertTrue(expected_symlink_path.is_symlink())
        self.assertEqual(
            dep_chart_dir.path, str(expected_symlink_path.resolve()))
