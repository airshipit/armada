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

import unittest

from armada.utils import schema


class SchemaTestCase(unittest.TestCase):
    def test_validate_load_schemas(self):
        expected_schemas = [
            'armada/Chart/v1', 'armada/ChartGroup/v1', 'armada/Manifest/v1'
            'armada/Chart/v2', 'armada/ChartGroup/v2', 'armada/Manifest/v2'
        ]
        for expected_schema in expected_schemas:
            self.assertIn(expected_schema, schema._SCHEMAS)

    def test_validate_load_duplicate_schemas_expect_runtime_error(self):
        """Validate that calling ``_load_schemas`` results in a
        ``RuntimeError`` being thrown, because the call is made during module
        import, and importing the schemas again in manually results in
        duplicates.
        """
        with self.assertRaisesRegexp(RuntimeError,
                                     'Duplicate schema specified for: .*'):
            schema._load_schemas()
