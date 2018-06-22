# Copyright 2018 The Armada Authors.
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

from armada import const

TESTRUN_STATUS_UNKNOWN = 0
TESTRUN_STATUS_SUCCESS = 1
TESTRUN_STATUS_FAILURE = 2
TESTRUN_STATUS_RUNNING = 3


def test_release_for_success(tiller,
                             release,
                             timeout=const.DEFAULT_TILLER_TIMEOUT,
                             cleanup=False):
    test_suite_run = tiller.test_release(
        release, timeout=timeout, cleanup=cleanup)
    results = getattr(test_suite_run, 'results', [])
    failed_results = [r for r in results if r.status != TESTRUN_STATUS_SUCCESS]
    return len(failed_results) == 0
