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

from armada.exceptions import base_exception


class ChartBuilderException(base_exception.ArmadaBaseException):
    '''Base class for the Chartbuilder handler exception and error handling.'''

    message = 'An unknown Armada handler error occurred.'


class HelmChartBuildException(ChartBuilderException):
    '''
    Exception that occurs when Helm Chart fails to build.
    '''

    def __init__(self, chart_name, details):
        self._chart_name = chart_name
        self._message = (
            'Failed to build Helm chart for {chart_name}. '
            'Details: {details}'.format(
                **{
                    'chart_name': chart_name,
                    'details': details
                }))

        super(HelmChartBuildException, self).__init__(self._message)
