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
ARMADA_CONTAINER_NAME=armada_test_$(date +%Y%m%d%H%M%s%s)

function generate_conf {
    tox -e genconfig > /dev/null
    tox -e genpolicy > /dev/null
    ETCDIR=$(mktemp -d)/armada
    mkdir -p ${ETCDIR} > /dev/null
    cp etc/armada/armada.conf.sample ${ETCDIR}/armada.conf
    cp etc/armada/api-paste.ini ${ETCDIR}/api-paste.ini
    cp etc/armada/policy.yaml.sample ${ETCDIR}/policy.yaml
    echo ${ETCDIR}
}

function test_armada {
    TMPETC=$1
    # Remove all containers with names starting with armada_test
    docker ps -a --filter "name=^/armada_test" --format "{{.ID}}" | xargs -r docker rm -f

    docker run \
      -d --name "${ARMADA_CONTAINER_NAME}" --net host \
      -v ${TMPETC}:/etc/armada \
      ${IMAGE}

    sleep 10

    RESULT=$(curl --noproxy '*' -i 'http://127.0.0.1:8000/api/v1.0/health' 2>/dev/null | tr '\r' '\n' | head -1)
    GOOD="HTTP/1.1 204 No Content"
    if [[ "${RESULT}" != "${GOOD}" ]]; then
      if docker exec -t ${CONTAINER_NAME} /bin/bash -c "curl -i 'http://127.0.0.1:8000/api/v1.0/health' --noproxy '*' | tr '\r' '\n' | head -1 "; then
        RESULT="${GOOD}"
      fi
    fi

    if [[ ${RESULT} == ${GOOD} ]]
    then
      RC=0
    else
      RC=1
    fi

    docker logs "${ARMADA_CONTAINER_NAME}"
    return $RC
}

function cleanup {
    TMPDIR=$1
    docker stop "${ARMADA_CONTAINER_NAME}"
    docker rm "${ARMADA_CONTAINER_NAME}"
   rm -rf $TMPDIR
}

TMPETC=$(generate_conf)

test_armada $TMPETC
RC=$?

cleanup $TMPETC

exit $RC
