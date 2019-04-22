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

import os
import pkg_resources
import re
import yaml

# Types
TYPE_CHART = 'Chart'
TYPE_CHARTGROUP = 'ChartGroup'
TYPE_MANIFEST = 'Manifest'

# Versions
VERSION_FORMAT = r'^v(\d+)$'
VERSION_MIN = 1
VERSION_MAX = 2

# Creates a mapping between ``metadata.name``: ``data`` where the
# ``metadata.name`` is the ``schema`` of a manifest and the ``data`` is the
# JSON schema to be used to validate the manifest in question.
_SCHEMAS = {}


class SchemaInfo(object):

    def __init__(self, type, version, data):
        self.type = type
        self.version = version
        self.data = data

    def __eq__(self, other):
        return self.type == other.type and self.version == other.version


def get_schema_info(name):
    return _SCHEMAS.get(name)


def _get_schema_info(name, data):
    parts = name.split('/')
    prefix, type, version_string = parts
    version_match = re.search(VERSION_FORMAT, version_string)
    version = int(version_match.group(1))
    return SchemaInfo(type, version, data)


def _get_schema_dir():
    return pkg_resources.resource_filename('armada', 'schemas')


def _load_schemas():
    """Populates ``_SCHEMAS`` with the schemas defined in package
    ``armada.schemas``.

    """
    schema_dir = _get_schema_dir()
    for schema_file in os.listdir(schema_dir):
        with open(os.path.join(schema_dir, schema_file)) as f:
            for schema in yaml.safe_load_all(f):
                name = schema['metadata']['name']
                if name in _SCHEMAS:
                    raise RuntimeError(
                        'Duplicate schema specified for: %s.' % name)
                _SCHEMAS[name] = _get_schema_info(name, schema['data'])


# Fill the cache.
_load_schemas()
