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

from armada import const


class ChartDelete(object):
    def __init__(self, chart, release_name, tiller, purge=True):
        """Initialize a chart delete handler.

        :param chart: The armada chart document
        :param release_name: Name of a Helm release
        :param tiller: Tiller object
        :param purge: Whether to purge the release

        :type chart: object
        :type release_name: str
        :type tiller: Tiller object
        :type purge: bool
        """

        self.chart = chart
        self.release_name = release_name
        self.tiller = tiller
        self.purge = purge
        self.delete_config = self.chart.get('delete', {})
        # TODO(seaneagan): Consider allowing this to be a percentage of the
        # chart's `wait.timeout` so that the timeouts can scale together, and
        # likely default to some reasonable value, e.g. "50%".
        self.timeout = self.delete_config.get(
            'timeout', const.DEFAULT_DELETE_TIMEOUT)

    def get_timeout(self):
        return self.timeout

    def delete(self):
        """Delete the release associated with the chart"
        """
        self.tiller.uninstall_release(
            self.release_name, timeout=self.get_timeout(), purge=self.purge)
