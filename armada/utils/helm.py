# Copyright 2019 The Armada Authors.
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

TESTRUN_STATUS_UNKNOWN = 0
TESTRUN_STATUS_SUCCESS = 1
TESTRUN_STATUS_FAILURE = 2
TESTRUN_STATUS_RUNNING = 3

HELM_HOOK_ANNOTATION = 'helm.sh/hook'
# TODO: Eventually remove 'test-failure' as it is removed in Helm 3,
# leaving for now to ensure test runs leftover from Helm 2 get deleted
# and don't cause name conflicts.
HELM_TEST_HOOKS = ['test', 'test-success', 'test-failure']


def is_test_pod(pod):
    annotations = pod.metadata.annotations

    # Retrieve pod's Helm test hooks
    test_hooks = None
    if annotations:
        hook_string = annotations.get(HELM_HOOK_ANNOTATION)
        if hook_string:
            hooks = hook_string.split(',')
            test_hooks = [h for h in hooks if h in HELM_TEST_HOOKS]

    return bool(test_hooks)


def get_test_suite_run_success(test_suite_run):
    return all(
        r.status == TESTRUN_STATUS_SUCCESS for r in test_suite_run.results)
