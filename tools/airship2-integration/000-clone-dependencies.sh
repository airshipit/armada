#!/bin/bash
# Copyright 2020 AT&T Intellectual Property.  All other rights reserved.
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

set -xe

CURRENT_DIR="$(pwd)"
: "${INSTALL_PATH:="../"}"
cd ${INSTALL_PATH}
: "${OSH_INFRA_COMMIT:="dc58ef9dddd0326cc86229eda4e21e269adb31be"}"

# Clone openstack-helm-infra
git clone https://opendev.org/openstack/openstack-helm-infra.git
cd openstack-helm-infra
git checkout "${OSH_INFRA_COMMIT}"

cd "${CURRENT_DIR}"
