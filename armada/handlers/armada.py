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

import subprocess  # nosec
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from oslo_config import cfg
from oslo_log import log as logging
import yaml

from armada import const
from armada.conf import set_current_chart
from armada.exceptions import armada_exceptions
from armada.exceptions import override_exceptions
from armada.exceptions import validate_exceptions
from armada.handlers import metrics
from armada.handlers.chart_deploy import ChartDeploy
from armada.handlers.chart_download import ChartDownload
from armada.handlers.helm import HelmReleaseId
from armada.handlers.manifest import Manifest
from armada.handlers.override import Override
from armada.utils.release import release_prefixer

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
            helm,
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
        Initialize the Armada engine.

        :param List[dict] documents: Armada documents.
        :param bool disable_update_pre: Disable pre-update operations.
        :param bool disable_update_post: Disable post-update operations.
        :param bool enable_chart_cleanup: Clean up unmanaged charts.
        :param bool force_wait: Force to wait until all charts are
            deployed, rather than using each chart's specified wait policy.
        :param int timeout: Specifies overall time in seconds t to wait for
            charts until timing out.
        :param str target_manifest: The target manifest to run. Useful for
            specifying which manifest to run when multiple are available.
        :param int k8s_wait_attempts: The number of times to attempt waiting
            for pods to become ready.
        :param int k8s_wait_attempt_sleep: The time in seconds to sleep
            between attempts.
        '''

        self.enable_chart_cleanup = enable_chart_cleanup
        self.enable_operator = CONF.enable_operator
        self.force_wait = force_wait
        self.helm = helm
        try:
            self.documents = Override(
                documents, overrides=set_ovr,
                values=values).update_manifests()
        except (validate_exceptions.InvalidManifestException,
                override_exceptions.InvalidOverrideValueException):
            raise
        self.target_manifest = target_manifest
        self.manifest = Manifest(
            self.documents, target_manifest=target_manifest).get_manifest()
        self.chart_download = ChartDownload()
        self.chart_deploy = ChartDeploy(
            self.manifest, disable_update_pre, disable_update_post,
            k8s_wait_attempts, k8s_wait_attempt_sleep, timeout, self.helm)

    def pre_flight_ops(self):
        """Perform a series of checks and operations to ensure proper
        deployment.
        """
        LOG.info("Performing pre-flight operations.")

        # Clone the chart sources
        manifest_data = self.manifest.get(const.KEYWORD_DATA, {})
        for group in manifest_data.get(const.KEYWORD_GROUPS, []):
            for ch in group.get(const.KEYWORD_DATA).get(const.KEYWORD_CHARTS,
                                                        []):
                self.chart_download.get_chart(ch, manifest=self.manifest)

    def sync(self):
        '''
        Synchronize Helm with the Armada Config(s)
        '''
        manifest_name = self.manifest['metadata']['name']
        with metrics.APPLY.get_context(manifest_name):
            if self.enable_operator:
                return self._sync_with_operator()
            else:
                return self._sync()

    def _sync_with_operator(self):
        # TODO: add actual msg
        msg = {
            'install': [],
            'upgrade': [],
            'diff': [],
            'purge': [],
            'protected': []
        }

        tfile = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        yaml.safe_dump_all(self.documents, tfile)
        tfile.flush()
        tfile.close()

        command = ['armada-go', 'apply']
        if self.target_manifest != "":
            command.extend(
                ['--target-manifest', "{}".format(self.target_manifest)])
        command.append("{}".format(tfile.name))
        LOG.info('Running command=%s', command)
        try:
            with subprocess.Popen(  # nosec
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    bufsize=1, universal_newlines=True) as sp:
                for line in sp.stdout:
                    LOG.info(line.rstrip())
                sp.wait()
                if sp.returncode != 0:
                    raise subprocess.CalledProcessError(
                        sp.returncode, command, output=sp.stdout)
        except subprocess.CalledProcessError as e:
            LOG.info("armada-go apply exception: %s", e)
            raise armada_exceptions.ArmadaException(e)

        LOG.info('Done applying manifest.')
        return msg

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
                        chart, cg_test_all_charts, prefix, concurrency)
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

        self.chart_download.cleanup()

    def _chart_cleanup(self, prefix, chart_groups, msg):
        LOG.info('Processing chart cleanup to remove unspecified releases.')

        valid_release_ids = []
        for group in chart_groups:
            group_data = group.get(const.KEYWORD_DATA, {})
            for chart in group_data.get(const.KEYWORD_CHARTS, []):
                chart_data = chart.get(const.KEYWORD_DATA, {})
                valid_release_ids.append(
                    HelmReleaseId(
                        chart_data['namespace'],
                        release_prefixer(prefix, chart_data['release'])))

        actual_release_ids = self.helm.list_release_ids()
        release_diff = list(set(actual_release_ids) - set(valid_release_ids))

        for release_id in release_diff:
            if release_id.name.startswith(prefix):
                LOG.info(
                    'Purging release %s as part of chart cleanup.', release_id)
                self.helm.uninstall_release(release_id)
                msg['purge'].append('{}'.format(release_id))
