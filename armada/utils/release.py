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

import time

import dateutil


def release_prefixer(prefix, release):
    '''
    attach prefix to release name
    '''
    return "{}-{}".format(prefix, release)


def label_selectors(labels):
    """
    :param labels: dictionary containing k, v

    :return: string of k8s labels
    """
    return ",".join(["%s=%s" % (k, v) for k, v in labels.items()])


def get_release_status(release):
    """
    :param release: helm release metadata

    :return: status name of release
    """

    return release['info']['status']


def get_last_test_result(release):
    """
    :param release: helm release metadata

    :return: whether tests are successful (no tests defined implies success)
    """
    test_hooks = (
        hook for hook in release.get('hooks', []) if any(
            e in ['test', 'test-success'] for e in hook['events']))
    return all(test['last_run']['phase'] == 'Succeeded' for test in test_hooks)


def get_last_deployment_age(release):
    """
    :param release: protobuf release object

    :return: age in seconds of last deployment of release
    """

    last_deployed_str = release['info']['last_deployed']
    last_deployed = dateutil.parser.isoparse(last_deployed_str).timestamp()
    now = int(time.time())
    last_deployment_age = now - last_deployed

    return last_deployment_age
