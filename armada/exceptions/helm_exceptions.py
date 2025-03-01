# Copyright 2021 The Armada Authors.
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

from armada.exceptions.base_exception import ArmadaBaseException as ex


class HelmCommandException(ex):
    '''
    Exception that occurs when a helm command fails.
    '''
    def __init__(self, called_process_error):
        self.called_process_error = called_process_error
        message = 'helm command failed: {}'.format(
            self.called_process_error.stderr)
        super(HelmCommandException, self).__init__(message)
