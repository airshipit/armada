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

import os
from pathlib import Path
from shutil import rmtree

from oslo_config import cfg
from oslo_log import log as logging

from armada import const
from armada.exceptions import chartbuilder_exceptions

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class ChartBuilder(object):
    '''
    This class handles taking chart intentions as a parameter and turning those
    into proper Helm chart metadata.
    '''
    @classmethod
    def from_chart_doc(cls, chart, helm):
        '''
        Returns a ChartBuilder defined by an Armada Chart doc.

        :param chart: Armada Chart doc for which to build the Helm chart.
        '''

        name = chart['metadata']['name']
        chart_data = chart[const.KEYWORD_DATA]
        source_dir = chart_data['source_dir']
        source_directory = os.path.join(*source_dir)
        dependencies = chart_data.get('dependencies')

        if dependencies is not None:
            # Ensure `charts` dir exists and is empty.
            charts_dir = os.path.join(source_directory, 'charts')
            charts_path = Path(charts_dir)
            if charts_path.is_dir():
                # NOTE: Ideally we would only delete the subcharts being
                # overridden, and leave the others in place, but we delete all
                # for backward compatibility with the Helm 2 based Armada.
                rmtree(charts_dir)
            charts_path.mkdir()

            # Add symlinks to dependencies into `charts` dir.
            for chart_dep in dependencies:
                # Handle any recursive dependencies.
                ChartBuilder.from_chart_doc(chart_dep, helm)

                dep_data = chart_dep[const.KEYWORD_DATA]
                dep_source_dir = dep_data['source_dir']
                dep_source_directory = os.path.join(*dep_source_dir)
                dep_charts_yaml = helm.show_chart(dep_source_directory)
                dep_name = dep_charts_yaml['name']
                dep_target_directory = os.path.join(charts_dir, dep_name)
                Path(dep_target_directory).symlink_to(dep_source_directory)

        return cls(name, source_directory, helm)

    def __init__(self, name, source_directory, helm):
        '''
        :param name: A name to use for the chart.
        :param source_directory: The source directory of the Helm chart.
        :param helm: Helm client to calculate the helm chart object.
        '''
        self.name = name
        self.source_directory = source_directory
        self.helm = helm

        # cache for generated chart object
        self._helm_chart = None

    # We do a dry-run upgrade here to get the helm chart metadata.
    # Ideally helm would support an explicit machine readable way to
    # get that data so we don't need the dry run upgrade which could
    # fail for other reasons than not being able to get the chart
    # metadata, see:
    #   https://github.com/helm/helm/issues/9968
    def get_helm_chart(self, release_id, values):
        '''Return a Helm chart object.
        '''
        LOG.debug(
            "Building chart %s from path %s", self.name, self.source_directory)
        try:
            result = self.helm.upgrade_release(
                self.source_directory, release_id, values=values, dry_run=True)
            return result['chart']
        except Exception as e:
            raise chartbuilder_exceptions.HelmChartBuildException(
                self.name, details=e)
