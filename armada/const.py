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

# Keywords
KEYWORD_DATA = 'data'
KEYWORD_PREFIX = 'release_prefix'
KEYWORD_GROUPS = 'chart_groups'
KEYWORD_CHARTS = 'chart_group'
KEYWORD_RELEASE = 'release'

# Armada
DEFAULT_CHART_TIMEOUT = 900
DEFAULT_TEST_TIMEOUT = 300

# Tiller
DEFAULT_TILLER_TIMEOUT = 300
DEFAULT_DELETE_TIMEOUT = DEFAULT_TILLER_TIMEOUT
STATUS_UNKNOWN = 'UNKNOWN'
STATUS_DEPLOYED = 'DEPLOYED'
STATUS_DELETED = 'DELETED'
STATUS_DELETING = 'DELETING'
STATUS_FAILED = 'FAILED'
STATUS_PENDING_INSTALL = 'PENDING_INSTALL'
STATUS_PENDING_UPGRADE = 'PENDING_UPGRADE'
STATUS_PENDING_ROLLBACK = 'PENDING_ROLLBACK'
STATUS_ALL = [
    STATUS_UNKNOWN, STATUS_DEPLOYED, STATUS_DELETED, STATUS_DELETING,
    STATUS_FAILED, STATUS_PENDING_INSTALL, STATUS_PENDING_UPGRADE,
    STATUS_PENDING_ROLLBACK
]

# Kubernetes
DEFAULT_K8S_TIMEOUT = 300

# Configuration File
CONFIG_PATH = '/etc/armada'
