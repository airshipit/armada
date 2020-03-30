# Copyright 2020 The Armada Authors.
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

from oslo_config import cfg
from oslo_log import log as logging

from armada import const
from armada.exceptions import source_exceptions
from armada.handlers import metrics
from armada.utils import source

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class ChartDownload():
    def __init__(self):
        self.chart_cache = {}

    def get_chart(self, ch, manifest=None):
        manifest_name = manifest['metadata']['name'] if manifest else None
        chart_name = ch['metadata']['name']
        with metrics.CHART_DOWNLOAD.get_context(manifest_name, chart_name):
            return self._get_chart(ch, manifest)

    def _get_chart(self, ch, manifest):
        chart = ch.get(const.KEYWORD_DATA)
        chart_source = chart.get('source', {})
        location = chart_source.get('location')
        ct_type = chart_source.get('type')
        subpath = chart_source.get('subpath', '.')
        proxy_server = chart_source.get('proxy_server')

        if ct_type == 'local':
            chart['source_dir'] = (location, subpath)
        elif ct_type == 'tar':
            source_key = (ct_type, location)

            if source_key not in self.chart_cache:
                LOG.info(
                    "Downloading tarball from: %s / proxy %s", location,
                    proxy_server or "not set")

                if not CONF.certs:
                    LOG.warn(
                        'Disabling server validation certs to extract charts')
                    tarball_dir = source.get_tarball(
                        location, verify=False, proxy_server=proxy_server)
                else:
                    tarball_dir = source.get_tarball(
                        location, verify=CONF.certs, proxy_server=proxy_server)
                self.chart_cache[source_key] = tarball_dir
            chart['source_dir'] = (self.chart_cache.get(source_key), subpath)
        elif ct_type == 'git':
            reference = chart_source.get('reference', 'master')
            source_key = (ct_type, location, reference)

            if source_key not in self.chart_cache:
                auth_method = chart_source.get('auth_method')

                logstr = 'Cloning repo: {} from branch: {}'.format(
                    location, reference)
                if proxy_server:
                    logstr += ' proxy: {}'.format(proxy_server)
                if auth_method:
                    logstr += ' auth method: {}'.format(auth_method)
                LOG.info(logstr)

                repo_dir = source.git_clone(
                    location,
                    reference,
                    proxy_server=proxy_server,
                    auth_method=auth_method)

                self.chart_cache[source_key] = repo_dir
            chart['source_dir'] = (self.chart_cache.get(source_key), subpath)
        else:
            name = ch['metadata']['name']
            raise source_exceptions.ChartSourceException(ct_type, name)

        for dep in ch.get(const.KEYWORD_DATA, {}).get('dependencies', []):
            self.get_chart(dep, manifest=manifest)

    def cleanup(self):
        '''
        Operations to run after deployment process has terminated
        '''
        LOG.info("Performing post-flight operations.")

        # Delete temp dirs used for deployment
        for chart_dir in self.chart_cache.values():
            LOG.debug('Removing temp chart directory: %s', chart_dir)
            source.source_cleanup(chart_dir)
