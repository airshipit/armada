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


class ArmadaException(base_exception.ArmadaBaseException):
    '''Base class for Armada handler exception and error handling.'''

    message = 'An unknown Armada handler error occurred.'


class ArmadaTimeoutException(ArmadaException):
    '''Exception that occurs when Armada times out while processing.'''

    def __init__(self, reason):
        self._message = 'Armada timed out waiting on: %s' % (reason)
        super(ArmadaTimeoutException, self).__init__(self._message)


class ProtectedReleaseException(ArmadaException):
    '''
    Exception that occurs when Armada encounters a release with status other
    than DEPLOYED that is designated `protected` in the Chart and
    `continue_processing` is False.
    '''

    def __init__(self, release, status):
        self._message = (
            'Armada encountered protected release {} in {} status'.format(
                release, status))
        super(ProtectedReleaseException, self).__init__(self._message)


class InvalidValuesYamlException(ArmadaException):
    '''
    Exception that occurs when Armada encounters invalid values.yaml content in
    a helm chart.
    '''

    def __init__(self, chart_description):
        self._message = (
            'Armada encountered invalid values.yaml in helm chart: %s'
            % chart_description)
        super(InvalidValuesYamlException, self).__init__(self._message)


class InvalidOverrideValuesYamlException(ArmadaException):
    '''
    Exception that occurs when Armada encounters invalid override yaml in
    helm chart.
    '''

    def __init__(self, chart_description):
        self._message = (
            'Armada encountered invalid values.yaml in helm chart: %s'
            % chart_description)
        super(InvalidValuesYamlException, self).__init__(self._message)


class ChartDeployException(ArmadaException):
    '''
    Exception that occurs while deploying charts.
    '''

    def __init__(self, chart_names):
        self._message = ('Exception deploying charts: %s' % chart_names)
        super(ChartDeployException, self).__init__(self._message)


class WaitException(ArmadaException):
    '''
    Exception that occurs while waiting for resources to become ready.
    '''

    def __init__(self, message):
        self._message = message
        super(WaitException, self).__init__(message)


class DeploymentLikelyPendingException(ArmadaException):
    '''
    Exception that occurs when it is detected that an existing release
    operation (e.g. install, update, rollback, delete) is likely still pending.
    '''

    def __init__(self, release, status, last_deployment_age, timeout):
        self._message = (
            'Existing deployment likely pending '
            'release={}, status={}, '
            '(last deployment age={}s) < (chart wait timeout={}s)'.format(
                release, status, last_deployment_age, timeout))
        super(DeploymentLikelyPendingException, self).__init__(self._message)
