#!/bin/bash
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
#
set -x

IMAGE=$1
USE_PROXY=${USE_PROXY:-false}
CONTAINER_NAME=armada_test_$(date +%Y%m%d%H%M%s%s)

docker create \
    -p 8000:8000 \
    --name ${CONTAINER_NAME} ${IMAGE}

docker start ${CONTAINER_NAME} &
sleep 5

# If the image build pipeline is running in a pod/docker (docker-in-docker),
# we'll need to exec into the nested container's network namespace to acces the
# armada api.
GOOD="HTTP/1.1 204 No Content"
RESULT="$(curl -i 'http://127.0.0.1:8000/api/v1.0/health' --noproxy '*' | tr '\r' '\n' | head -1)"
if [[ "${RESULT}" != "${GOOD}" ]]; then
  if docker exec -t ${CONTAINER_NAME} /bin/bash -c "curl -i 'http://127.0.0.1:8000/api/v1.0/health' --noproxy '*' | tr '\r' '\n' | head -1 "; then
    RESULT="${GOOD}"
  fi
fi

docker stop ${CONTAINER_NAME}
docker logs ${CONTAINER_NAME}
docker rm ${CONTAINER_NAME}

if [[ ${RESULT} == ${GOOD} ]]; then
    exit 0
else
    exit 1
fi