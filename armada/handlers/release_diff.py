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

        old_input = self.make_release_input(self.old_chart, self.old_values)
        new_input = self.make_release_input(self.new_chart, self.new_values)

        return DeepDiff(old_input, new_input, view='tree')

    def make_release_input(self, chart, values):
        return {'chart': chart, 'values': values}
