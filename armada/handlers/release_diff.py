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

from deepdiff import DeepDiff
import yaml

from armada.exceptions import armada_exceptions


class ReleaseDiff(object):
    '''
    A utility for discovering diffs in helm release inputs, for example to
    determine whether an upgrade is needed and what specific changes will be
    applied.

    Release inputs which are relevant are the override values given, and
    the chart content including:

    * default values (values.yaml),
    * templates and their content
    * files and their content
    * the above for each chart on which the chart depends transitively.

    This excludes Chart.yaml content as that is rarely used by the chart
    via ``{{ .Chart }}``, and even when it is does not usually necessitate
    an upgrade.

    :param old_chart: The deployed chart.
    :type  old_chart: Chart
    :param old_values: The deployed chart override values.
    :type  old_values: dict
    :param new_chart: The chart to deploy.
    :type  new_chart: Chart
    :param new_values: The chart override values to deploy.
    :type  new_values: dict
    '''

    def __init__(self, old_chart, old_values, new_chart, new_values):
        self.old_chart = old_chart
        self.old_values = old_values
        self.new_chart = new_chart
        self.new_values = new_values

    def get_diff(self):
        '''
        Get the diff.

        :return: Mapping of difference types to sets of those differences.
        :rtype: dict
        '''

        old_input = self.make_release_input(self.old_chart, self.old_values,
                                            'previously deployed')
        new_input = self.make_release_input(self.new_chart, self.new_values,
                                            'currently being deployed')

        return DeepDiff(old_input, new_input, view='tree')

    def make_release_input(self, chart, values, desc):
        return {'chart': self.make_chart_dict(chart, desc), 'values': values}

    def make_chart_dict(self, chart, desc):
        try:
            default_values = yaml.safe_load(chart.values.raw)
        except yaml.YAMLError:
            chart_desc = '{} ({})'.format(chart.metadata.name, desc)
            raise armada_exceptions.InvalidValuesYamlException(chart_desc)
        files = {f.type_url: f.value for f in chart.files}
        templates = {t.name: t.data for t in chart.templates}
        dependencies = {
            d.metadata.name: self.make_chart_dict(
                d, '{}({} dependency)'.format(desc, d.metadata.name))
            for d in chart.dependencies
        }

        return {
            # TODO(seaneagan): Are there use cases to include other
            # `chart.metadata` (Chart.yaml) fields? If so, could include option
            # under `upgrade` key in armada chart schema for this. Or perhaps
            # can even add `upgrade.always` there to handle dynamic things
            # used in charts like dates, environment variables, etc.
            'name': chart.metadata.name,
            'values': default_values,
            'files': files,
            'templates': templates,
            'dependencies': dependencies
        }
