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

from concurrent.futures import ThreadPoolExecutor, as_completed

from oslo_config import cfg
from oslo_log import log as logging

from armada import const
from armada.conf import set_current_chart
from armada.exceptions import armada_exceptions
from armada.exceptions import override_exceptions
from armada.exceptions import source_exceptions
from armada.exceptions import tiller_exceptions
from armada.exceptions import validate_exceptions
from armada.handlers import metrics
from armada.handlers.chart_deploy import ChartDeploy
from armada.handlers.manifest import Manifest
from armada.handlers.override import Override
from armada.utils.release import release_prefixer
from armada.utils import source

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class Armada(object):
    '''
    This is the main Armada class handling the Armada
    workflows
    '''

    def __init__(
            self,
            documents,
            tiller,
            disable_update_pre=False,
            disable_update_post=False,
            enable_chart_cleanup=False,
            set_ovr=None,
            force_wait=False,
            timeout=None,
            values=None,
            target_manifest=None,
            k8s_wait_attempts=1,
            k8s_wait_attempt_sleep=1):
        '''
        Initialize the Armada engine and establish a connection to Tiller.

        :param List[dict] documents: Armada documents.
        :param tiller: Tiller instance to use.
        :param bool disable_update_pre: Disable pre-update Tiller operations.
        :param bool disable_update_post: Disable post-update Tiller
            operations.
        :param bool enable_chart_cleanup: Clean up unmanaged charts.
        :param bool force_wait: Force Tiller to wait until all charts are
            deployed, rather than using each chart's specified wait policy.
        :param int timeout: Specifies overall time in seconds that Tiller
            should wait for charts until timing out.
        :param str target_manifest: The target manifest to run. Useful for
            specifying which manifest to run when multiple are available.
        :param int k8s_wait_attempts: The number of times to attempt waiting
            for pods to become ready.
        :param int k8s_wait_attempt_sleep: The time in seconds to sleep
            between attempts.
        '''

        self.enable_chart_cleanup = enable_chart_cleanup
        self.force_wait = force_wait
        self.tiller = tiller
        try:
            self.documents = Override(
                documents, overrides=set_ovr,
                values=values).update_manifests()
        except (validate_exceptions.InvalidManifestException,
                override_exceptions.InvalidOverrideValueException):
            raise
        self.manifest = Manifest(
            self.documents, target_manifest=target_manifest).get_manifest()
        self.chart_cache = {}
        self.chart_deploy = ChartDeploy(
            self.manifest, disable_update_pre, disable_update_post,
            k8s_wait_attempts, k8s_wait_attempt_sleep, timeout, self.tiller)

    def pre_flight_ops(self):
        """Perform a series of checks and operations to ensure proper
        deployment.
        """
        LOG.info("Performing pre-flight operations.")

        # Ensure Tiller is available and manifest is valid
        if not self.tiller.tiller_status():
            raise tiller_exceptions.TillerServicesUnavailableException()

        # Clone the chart sources
        manifest_data = self.manifest.get(const.KEYWORD_DATA, {})
        for group in manifest_data.get(const.KEYWORD_GROUPS, []):
            for ch in group.get(const.KEYWORD_DATA).get(const.KEYWORD_CHARTS,
                                                        []):
                self.get_chart(ch)

    def get_chart(self, ch):
        manifest_name = self.manifest['metadata']['name']
        chart_name = ch['metadata']['name']
        with metrics.CHART_DOWNLOAD.get_context(manifest_name, chart_name):
            return self._get_chart(ch)

    def _get_chart(self, ch):
        chart = ch.get(const.KEYWORD_DATA)
        chart_source = chart.get('source', {})
        location = chart_source.get('location')
        ct_type = chart_source.get('type')
        subpath = chart_source.get('subpath', '.')

        if ct_type == 'local':
            chart['source_dir'] = (location, subpath)
        elif ct_type == 'tar':
            source_key = (ct_type, location)

            if source_key not in self.chart_cache:
                LOG.info('Downloading tarball from: %s', location)

                if not CONF.certs:
                    LOG.warn(
                        'Disabling server validation certs to extract charts')
                    tarball_dir = source.get_tarball(location, verify=False)
                else:
                    tarball_dir = source.get_tarball(
                        location, verify=CONF.certs)
                self.chart_cache[source_key] = tarball_dir
            chart['source_dir'] = (self.chart_cache.get(source_key), subpath)
        elif ct_type == 'git':
            reference = chart_source.get('reference', 'master')
            source_key = (ct_type, location, reference)

            if source_key not in self.chart_cache:
                auth_method = chart_source.get('auth_method')
                proxy_server = chart_source.get('proxy_server')

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
            self.get_chart(dep)

    def sync(self):
        '''
        Synchronize Helm with the Armada Config(s)
        '''
        manifest_name = self.manifest['metadata']['name']
        with metrics.APPLY.get_context(manifest_name):
            return self._sync()

    def _sync(self):
        msg = {
            'install': [],
            'upgrade': [],
            'diff': [],
            'purge': [],
            'protected': []
        }

        # TODO: (gardlt) we need to break up this func into
        # a more cleaner format
        self.pre_flight_ops()

        known_releases = self.tiller.list_releases()

        manifest_data = self.manifest.get(const.KEYWORD_DATA, {})
        prefix = manifest_data.get(const.KEYWORD_PREFIX)

        for cg in manifest_data.get(const.KEYWORD_GROUPS, []):
            chartgroup = cg.get(const.KEYWORD_DATA)
            cg_name = cg.get('metadata').get('name')
            cg_desc = chartgroup.get('description', '<missing description>')
            cg_sequenced = chartgroup.get(
                'sequenced', False) or self.force_wait

            LOG.info(
                'Processing ChartGroup: %s (%s), sequenced=%s%s', cg_name,
                cg_desc, cg_sequenced, ' (forced)' if self.force_wait else '')

            # TODO: Remove when v1 doc support is removed.
            cg_test_all_charts = chartgroup.get('test_charts')

            cg_charts = chartgroup.get(const.KEYWORD_CHARTS, [])

            def deploy_chart(chart, concurrency):
                set_current_chart(chart)
                try:
                    return self.chart_deploy.execute(
                        chart, cg_test_all_charts, prefix, known_releases,
                        concurrency)
                finally:
                    set_current_chart(None)

            results = []
            failures = []

            # Returns whether or not there was a failure
            def handle_result(chart, get_result):
                name = chart['metadata']['name']
                try:
                    result = get_result()
                except Exception:
                    LOG.exception('Chart deploy [{}] failed'.format(name))
                    failures.append(name)
                    return True
                else:
                    results.append(result)
                    return False

            if cg_sequenced:
                for chart in cg_charts:
                    if (handle_result(chart, lambda: deploy_chart(chart, 1))):
                        break
            else:
                with ThreadPoolExecutor(
                        max_workers=len(cg_charts)) as executor:
                    future_to_chart = {
                        executor.submit(deploy_chart, chart, len(cg_charts)):
                        chart
                        for chart in cg_charts
                    }

                    for future in as_completed(future_to_chart):
                        chart = future_to_chart[future]
                        handle_result(chart, future.result)

            if failures:
                LOG.error('Chart deploy(s) failed: %s', failures)
                raise armada_exceptions.ChartDeployException(failures)

            for result in results:
                for k, v in result.items():
                    msg[k].append(v)

            # End of Charts in ChartGroup
            LOG.info('All Charts applied in ChartGroup %s.', cg_name)

        self.post_flight_ops()

        if self.enable_chart_cleanup:
            self._chart_cleanup(
                prefix,
                self.manifest[const.KEYWORD_DATA][const.KEYWORD_GROUPS], msg)

        LOG.info('Done applying manifest.')
        return msg

    def post_flight_ops(self):
        '''
        Operations to run after deployment process has terminated
        '''
        LOG.info("Performing post-flight operations.")

        # Delete temp dirs used for deployment
        for chart_dir in self.chart_cache.values():
            LOG.debug('Removing temp chart directory: %s', chart_dir)
            source.source_cleanup(chart_dir)

    def _chart_cleanup(self, prefix, chart_groups, msg):
        LOG.info('Processing chart cleanup to remove unspecified releases.')

        valid_releases = []
        for group in chart_groups:
            group_data = group.get(const.KEYWORD_DATA, {})
            for chart in group_data.get(const.KEYWORD_CHARTS, []):
                chart_data = chart.get(const.KEYWORD_DATA, {})
                valid_releases.append(
                    release_prefixer(prefix, chart_data.get('release')))

        actual_releases = [x.name for x in self.tiller.list_releases()]
        release_diff = list(set(actual_releases) - set(valid_releases))

        for release in release_diff:
            if release.startswith(prefix):
                LOG.info(
                    'Purging release %s as part of chart cleanup.', release)
                self.tiller.uninstall_release(release)
                msg['purge'].append(release)
