# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
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

import mock

from armada.handlers.release_diff import ReleaseDiff
from armada.tests.unit import base


# Test diffs (or absence of) in top-level chart / values.
class ReleaseDiffTestCase(base.ArmadaTestCase):
    def test_same_input(self):
        diff = ReleaseDiff(
            mock.sentinel.chart, mock.sentinel.values, mock.sentinel.chart,
            mock.sentinel.values).get_diff()
        self.assertFalse(diff)

    def test_diff_input(self):
        diff = ReleaseDiff(
            mock.sentinel.old_chart, mock.sentinel.old_values,
            mock.sentinel.new_chart, mock.sentinel.new_values).get_diff()
        self.assertTrue(diff)
