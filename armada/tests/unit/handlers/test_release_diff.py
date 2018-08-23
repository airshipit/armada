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

from armada.handlers.release_diff import ReleaseDiff
from armada.tests.unit import base

from google.protobuf.any_pb2 import Any
from hapi.chart.chart_pb2 import Chart
from hapi.chart.config_pb2 import Config
from hapi.chart.metadata_pb2 import Metadata
from hapi.chart.template_pb2 import Template


# Tests for diffs which can occur in both top-level or dependency charts,
# and thus are inherited by both of those test classes.
class _BaseReleaseDiffTestCase():

    def setUp(self):
        super(base.ArmadaTestCase, self).setUp()
        self.old_chart = self.make_chart()
        self.old_values = self.make_values()

    def make_chart(self):
        chart = self._make_chart()
        dep = self._make_chart()
        dep.metadata.name = 'dep1'
        sub_dep = self._make_chart()
        sub_dep.metadata.name = 'dep1'
        sub_sub_dep = self._make_chart()
        sub_sub_dep.metadata.name = 'dep1'
        sub_dep.dependencies.extend([sub_sub_dep])
        dep.dependencies.extend([sub_dep])
        chart.dependencies.extend([dep])
        return chart

    def _make_chart(self):
        return Chart(
            metadata=Metadata(
                description='chart description',
                name='chart_name',
                version='0.1.2'),
            templates=[
                Template(
                    name='template_name', data='template content'.encode())
            ],
            files=[
                Any(type_url='./file_name.ext', value='file content'.encode())
            ],
            dependencies=[],
            values=Config(raw='{param: d1}'))

    def make_values(self):
        return {'param': 'o1'}

    def _test_chart_diff(self, update_chart):
        new_chart = self.make_chart()
        chart_to_update = self.get_chart_to_update(new_chart)
        update_chart(chart_to_update)
        diff = ReleaseDiff(self.old_chart, self.old_values, new_chart,
                           self.old_values).get_diff()
        self.assertTrue(diff)

    def get_chart_to_update(self, chart):
        raise NotImplementedError('Implement in subclass')

    def test_metadata_non_name_diff_ignored(self):
        new_chart = self.make_chart()
        chart_to_update = self.get_chart_to_update(new_chart)
        chart_to_update.metadata.description = 'new chart description'
        diff = ReleaseDiff(self.old_chart, self.old_values, new_chart,
                           self.old_values).get_diff()
        self.assertFalse(diff)

    def test_metadata_name_diff(self):

        def update_chart(chart):
            chart.metadata.name = 'new_chart_name'

        self._test_chart_diff(update_chart)

    def test_default_values_diff(self):

        def update_chart(chart):
            chart.values.raw = '{param: d2}'

        self._test_chart_diff(update_chart)

    def test_template_name_diff(self):

        def update_chart(chart):
            chart.templates[0].name = 'new_template_name'

        self._test_chart_diff(update_chart)

    def test_template_data_diff(self):

        def update_chart(chart):
            chart.templates[0].data = 'new template content'.encode()

        self._test_chart_diff(update_chart)

    def test_add_template_diff(self):

        def update_chart(chart):
            chart.templates.extend([
                Template(
                    name='new_template_name',
                    data='new template content'.encode())
            ])

        self._test_chart_diff(update_chart)

    def test_remove_template_diff(self):

        def update_chart(chart):
            del chart.templates[0]

        self._test_chart_diff(update_chart)

    def test_file_type_url_diff(self):

        def update_chart(chart):
            chart.files[0].type_url = './new_file_name.ext'

        self._test_chart_diff(update_chart)

    def test_file_value_diff(self):

        def update_chart(chart):
            chart.files[0].value = 'new file content'.encode()

        self._test_chart_diff(update_chart)

    def test_add_file_diff(self):

        def update_chart(chart):
            chart.files.extend([
                Any(type_url='./new_file_name.ext',
                    value='new file content'.encode())
            ])

        self._test_chart_diff(update_chart)

    def test_remove_file_diff(self):

        def update_chart(chart):
            del chart.files[0]

        self._test_chart_diff(update_chart)

    def test_add_dependency_diff(self):

        def update_chart(chart):
            dep = self._make_chart()
            dep.metadata.name = 'dep2'
            chart.dependencies.extend([dep])

        self._test_chart_diff(update_chart)

    def test_remove_dependency_diff(self):

        def update_chart(chart):
            del chart.dependencies[0]

        self._test_chart_diff(update_chart)


# Test diffs (or absence of) in top-level chart / values.
class ReleaseDiffTestCase(_BaseReleaseDiffTestCase, base.ArmadaTestCase):

    def get_chart_to_update(self, chart):
        return chart

    def test_same_input_no_diff(self):
        diff = ReleaseDiff(self.old_chart, self.old_values, self.make_chart(),
                           self.make_values()).get_diff()
        self.assertFalse(diff)

    def test_override_values_diff(self):
        new_values = {'param': 'o2'}
        diff = ReleaseDiff(self.old_chart, self.old_values, self.old_chart,
                           new_values).get_diff()
        self.assertTrue(diff)


# Test diffs in dependencies.
class DependencyReleaseDiffTestCase(_BaseReleaseDiffTestCase,
                                    base.ArmadaTestCase):

    def get_chart_to_update(self, chart):
        return chart.dependencies[0]


# Test diffs in transitive dependencies.
class TransitiveDependencyReleaseDiffTestCase(_BaseReleaseDiffTestCase,
                                              base.ArmadaTestCase):

    def get_chart_to_update(self, chart):
        return chart.dependencies[0].dependencies[0]
