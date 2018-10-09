#!/bin/bash
#
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

set -ex

CMD="armada"

# Define port
ARMADA_UWSGI_PORT=${ARMADA_UWSGI_PORT:-8000}
# How long uWSGI should wait for each Armada response
ARMADA_UWSGI_TIMEOUT=${ARMADA_UWSGI_TIMEOUT:-"3600"}
# Number of uWSGI workers to handle API requests
ARMADA_UWSGI_WORKERS=${ARMADA_UWSGI_WORKERS:-"4"}
# Threads per worker
ARMADA_UWSGI_THREADS=${ARMADA_UWSGI_THREADS:-"1"}

# Start Armada application
# TODO(fmontei): Should be specifying callable too. But Armada spins up the
# server during import in `armada.api.server`.
if [ "$1" = 'server' ]; then
    exec uwsgi \
        -b 32768 \
        --die-on-term \
        --http :${ARMADA_UWSGI_PORT} \
        --http-timeout $ARMADA_UWSGI_TIMEOUT \
        --enable-threads \
        -L \
        --lazy-apps \
        --master \
        --paste config:/etc/armada/api-paste.ini \
        --pyargv "--config-file /etc/armada/armada.conf" \
        --threads $ARMADA_UWSGI_THREADS \
        --workers $ARMADA_UWSGI_WORKERS
else
    exec $CMD "$@"
fi
