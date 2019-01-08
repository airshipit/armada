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

from armada.utils.helm import get_test_suite_run_success

import time


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
    :param release: protobuf release object

    :return: status name of release
    """

    status = release.info.status
    return status.Code.Name(status.code)


def get_last_test_result(release):
    """
    :param release: protobuf release object

    :return: status name of release
    """

    status = release.info.status
    if not status.HasField('last_test_suite_run'):
        return None
    return get_test_suite_run_success(status.last_test_suite_run)


def get_last_deployment_age(release):
    """
    :param release: protobuf release object

    :return: age in seconds of last deployment of release
    """

    last_deployed = release.info.last_deployed.seconds
    now = int(time.time())
    last_deployment_age = now - last_deployed

    return last_deployment_age
