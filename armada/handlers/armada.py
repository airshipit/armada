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

import functools
import time
import yaml

from oslo_config import cfg
from oslo_log import log as logging

from armada import const
from armada.exceptions import armada_exceptions
from armada.exceptions import override_exceptions
from armada.exceptions import source_exceptions
from armada.exceptions import tiller_exceptions
from armada.exceptions import validate_exceptions
from armada.handlers.chartbuilder import ChartBuilder
from armada.handlers.manifest import Manifest
from armada.handlers.override import Override
from armada.handlers.release_diff import ReleaseDiff
from armada.handlers.test import test_release_for_success
from armada.handlers.tiller import Tiller
from armada.utils.release import release_prefixer
from armada.utils import source

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class Armada(object):
    '''
    This is the main Armada class handling the Armada
    workflows
    '''

    def __init__(self,
                 documents,
                 disable_update_pre=False,
                 disable_update_post=False,
                 enable_chart_cleanup=False,
                 dry_run=False,
                 set_ovr=None,
                 force_wait=False,
                 timeout=0,
                 tiller_host=None,
                 tiller_port=None,
                 tiller_namespace=None,
                 values=None,
                 target_manifest=None,
                 k8s_wait_attempts=1,
                 k8s_wait_attempt_sleep=1):
        '''
        Initialize the Armada engine and establish a connection to Tiller.

        :param List[dict] documents: Armada documents.
        :param bool disable_update_pre: Disable pre-update Tiller operations.
        :param bool disable_update_post: Disable post-update Tiller
            operations.
        :param bool enable_chart_cleanup: Clean up unmanaged charts.
        :param bool dry_run: Run charts without installing them.
        :param bool force_wait: Force Tiller to wait until all charts are
            deployed, rather than using each chart's specified wait policy.
        :param int timeout: Specifies overall time in seconds that Tiller
            should wait for charts until timing out.
        :param str tiller_host: Tiller host IP. Default is None.
        :param int tiller_port: Tiller host port. Default is
            ``CONF.tiller_port``.
        :param str tiller_namespace: Tiller host namespace. Default is
            ``CONF.tiller_namespace``.
        :param str target_manifest: The target manifest to run. Useful for
            specifying which manifest to run when multiple are available.
        :param int k8s_wait_attempts: The number of times to attempt waiting
            for pods to become ready.
        :param int k8s_wait_attempt_sleep: The time in seconds to sleep
            between attempts.
        '''
        tiller_port = tiller_port or CONF.tiller_port
        tiller_namespace = tiller_namespace or CONF.tiller_namespace

        self.disable_update_pre = disable_update_pre
        self.disable_update_post = disable_update_post
        self.enable_chart_cleanup = enable_chart_cleanup
        self.dry_run = dry_run
        self.force_wait = force_wait
        self.timeout = timeout
        # TODO: Use dependency injection i.e. pass in a Tiller instead of
        #       creating it here.
        self.tiller = Tiller(
            tiller_host=tiller_host,
            tiller_port=tiller_port,
            tiller_namespace=tiller_namespace,
            dry_run=dry_run)
        try:
            self.documents = Override(
                documents, overrides=set_ovr,
                values=values).update_manifests()
        except (validate_exceptions.InvalidManifestException,
                override_exceptions.InvalidOverrideValueException):
            raise
        self.k8s_wait_attempts = k8s_wait_attempts
        self.k8s_wait_attempt_sleep = k8s_wait_attempt_sleep
        self.manifest = Manifest(
            self.documents, target_manifest=target_manifest).get_manifest()
        self.cloned_dirs = set()

    def find_release_chart(self, known_releases, release_name):
        '''
        Find a release given a list of known_releases and a release name
        '''
        for release, _, chart, values, _ in known_releases:
            if release == release_name:
                return chart, values

    def pre_flight_ops(self):
        """Perform a series of checks and operations to ensure proper
        deployment.
        """
        LOG.info("Performing pre-flight operations.")

        # Ensure Tiller is available and manifest is valid
        if not self.tiller.tiller_status():
            raise tiller_exceptions.TillerServicesUnavailableException()

        # Clone the chart sources
        repos = {}
        manifest_data = self.manifest.get(const.KEYWORD_ARMADA, {})
        for group in manifest_data.get(const.KEYWORD_GROUPS, []):
            for ch in group.get(const.KEYWORD_CHARTS, []):
                self.tag_cloned_repo(ch, repos)

                for dep in ch.get('chart', {}).get('dependencies', []):
                    self.tag_cloned_repo(dep, repos)

    def tag_cloned_repo(self, ch, repos):
        chart = ch.get('chart', {})
        chart_source = chart.get('source', {})
        location = chart_source.get('location')
        ct_type = chart_source.get('type')
        subpath = chart_source.get('subpath', '.')

        if ct_type == 'local':
            chart['source_dir'] = (location, subpath)
        elif ct_type == 'tar':
            LOG.info('Downloading tarball from: %s', location)

            if not CONF.certs:
                LOG.warn('Disabling server validation certs to extract charts')
                tarball_dir = source.get_tarball(location, verify=False)
            else:
                tarball_dir = source.get_tarball(location, verify=CONF.cert)

            chart['source_dir'] = (tarball_dir, subpath)
        elif ct_type == 'git':
            reference = chart_source.get('reference', 'master')
            repo_branch = (location, reference)

            if repo_branch not in repos:
                auth_method = chart_source.get('auth_method')
                proxy_server = chart_source.get('proxy_server')

                logstr = 'Cloning repo: {} from branch: {}'.format(
                    *repo_branch)
                if proxy_server:
                    logstr += ' proxy: {}'.format(proxy_server)
                if auth_method:
                    logstr += ' auth method: {}'.format(auth_method)
                LOG.info(logstr)

                repo_dir = source.git_clone(
                    *repo_branch,
                    proxy_server=proxy_server,
                    auth_method=auth_method)
                self.cloned_dirs.add(repo_dir)

                repos[repo_branch] = repo_dir
                chart['source_dir'] = (repo_dir, subpath)
            else:
                chart['source_dir'] = (repos.get(repo_branch), subpath)
        else:
            chart_name = chart.get('chart_name')
            raise source_exceptions.ChartSourceException(ct_type, chart_name)

    def _get_releases_by_status(self):
        '''
        Return a list of current releases with DEPLOYED or FAILED status
        '''
        deployed_releases = []
        failed_releases = []
        known_releases = self.tiller.list_charts()
        for release in known_releases:
            if release[4] == const.STATUS_DEPLOYED:
                deployed_releases.append(release)
            elif release[4] == const.STATUS_FAILED:
                failed_releases.append(release)
            else:
                # tiller.list_charts() only looks at DEPLOYED/FAILED so
                # this should be unreachable
                LOG.debug('Ignoring release %s in status %s.', release[0],
                          release[4])

        return deployed_releases, failed_releases

    def sync(self):
        '''
        Synchronize Helm with the Armada Config(s)
        '''
        if self.dry_run:
            LOG.info('Armada is in DRY RUN mode, no changes being made.')

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

        # extract known charts on tiller right now
        deployed_releases, failed_releases = self._get_releases_by_status()

        manifest_data = self.manifest.get(const.KEYWORD_ARMADA, {})
        prefix = manifest_data.get(const.KEYWORD_PREFIX)

        for chartgroup in manifest_data.get(const.KEYWORD_GROUPS, []):
            cg_name = chartgroup.get('name', '<missing name>')
            cg_desc = chartgroup.get('description', '<missing description>')
            cg_sequenced = chartgroup.get('sequenced', False)
            LOG.info('Processing ChartGroup: %s (%s), sequenced=%s', cg_name,
                     cg_desc, cg_sequenced)

            # TODO(MarshM): Deprecate the `test_charts` key
            cg_test_all_charts = chartgroup.get('test_charts')
            if isinstance(cg_test_all_charts, bool):
                LOG.warn('The ChartGroup `test_charts` key is deprecated, '
                         'and support for this will be removed. See the '
                         'Chart `test` key for more information.')
            else:
                # This key defaults to True. Individual charts must
                # explicitly disable helm tests if they choose
                cg_test_all_charts = True

            ns_label_set = set()
            tests_to_run = []

            cg_charts = chartgroup.get(const.KEYWORD_CHARTS, [])

            # Track largest Chart timeout to stop the ChartGroup at the end
            cg_max_timeout = 0

            for chart_entry in cg_charts:
                chart = chart_entry.get('chart', {})
                namespace = chart.get('namespace')
                release = chart.get('release')
                release_name = release_prefixer(prefix, release)
                LOG.info('Processing Chart, release=%s', release_name)

                values = chart.get('values', {})
                pre_actions = {}
                post_actions = {}

                protected = chart.get('protected', {})
                p_continue = protected.get('continue_processing', False)

                # Check for existing FAILED release, and purge
                if release_name in [rel[0] for rel in failed_releases]:
                    LOG.info('Purging FAILED release %s before deployment.',
                             release_name)
                    if protected:
                        if p_continue:
                            LOG.warn(
                                'Release %s is `protected`, '
                                'continue_processing=True. Operator must '
                                'handle FAILED release manually.',
                                release_name)
                            msg['protected'].append(release_name)
                            continue
                        else:
                            LOG.error(
                                'Release %s is `protected`, '
                                'continue_processing=False.', release_name)
                            raise armada_exceptions.ProtectedReleaseException(
                                release_name)
                    else:
                        # Purge the release
                        self.tiller.uninstall_release(release_name)
                        msg['purge'].append(release_name)

                # NOTE(MarshM): Calculating `wait_timeout` is unfortunately
                #   overly complex. The order of precedence is currently:
                #   1) User provided override via API/CLI (default 0 if not
                #      provided by client/user).
                #   2) Chart's `data.wait.timeout`, or...
                #   3) Chart's `data.timeout` (deprecated).
                #   4) const.DEFAULT_CHART_TIMEOUT, if nothing is ever
                #      specified, for use in waiting for final ChartGroup
                #      health and helm tests, but ignored for the actual
                #      install/upgrade of the Chart.
                # NOTE(MarshM): Not defining a timeout has a side effect of
                #   allowing Armada to install charts with a circular
                #   dependency defined between components.

                # TODO(MarshM): Deprecated, remove the following block
                deprecated_timeout = chart.get('timeout', None)
                if isinstance(deprecated_timeout, int):
                    LOG.warn('The `timeout` key is deprecated and support '
                             'for this will be removed soon. Use '
                             '`wait.timeout` instead.')

                wait_values = chart.get('wait', {})
                wait_labels = wait_values.get('labels', {})
                wait_timeout = self.timeout
                if wait_timeout <= 0:
                    wait_timeout = wait_values.get('timeout', wait_timeout)
                    # TODO(MarshM): Deprecated, remove the following check
                    if wait_timeout <= 0:
                        wait_timeout = deprecated_timeout or wait_timeout

                # Determine wait logic
                # NOTE(Dan Kim): Conditions to wait are below :
                # 1) set sequenced=True in chart group
                # 2) set force_wait param
                # 3) add Chart's `data.wait.timeout`
                # --timeout param will do not set wait=True, it just change
                # max timeout of chart's deployment. (default: 900)
                this_chart_should_wait = (cg_sequenced or self.force_wait or
                                          (bool(wait_values) and
                                           (wait_timeout > 0)))

                # If there is still no timeout, we need to use a default
                # (item 4 in note above)
                if wait_timeout <= 0:
                    LOG.warn('No Chart timeout specified, using default: %ss',
                             const.DEFAULT_CHART_TIMEOUT)
                    wait_timeout = const.DEFAULT_CHART_TIMEOUT

                # Naively take largest timeout to apply at end
                # TODO(MarshM) better handling of timeout/timer
                cg_max_timeout = max(wait_timeout, cg_max_timeout)

                test_chart_override = chart.get('test')
                # Use old default value when not using newer `test` key
                test_cleanup = True
                if test_chart_override is None:
                    test_this_chart = cg_test_all_charts
                elif isinstance(test_chart_override, bool):
                    LOG.warn('Boolean value for chart `test` key is'
                             ' deprecated and support for this will'
                             ' be removed. Use `test.enabled` '
                             'instead.')
                    test_this_chart = test_chart_override
                else:
                    # NOTE: helm tests are enabled by default
                    test_this_chart = test_chart_override.get('enabled', True)
                    test_cleanup = test_chart_override.get('options', {}).get(
                        'cleanup', False)

                chartbuilder = ChartBuilder(chart)
                new_chart = chartbuilder.get_helm_chart()

                # Begin Chart timeout deadline
                deadline = time.time() + wait_timeout

                # TODO(mark-burnett): It may be more robust to directly call
                # tiller status to decide whether to install/upgrade rather
                # than checking for list membership.
                if release_name in [rel[0] for rel in deployed_releases]:

                    # indicate to the end user what path we are taking
                    LOG.info("Upgrading release %s in namespace %s",
                             release_name, namespace)
                    # extract the installed chart and installed values from the
                    # latest release so we can compare to the intended state
                    old_chart, old_values_string = self.find_release_chart(
                        deployed_releases, release_name)

                    upgrade = chart.get('upgrade', {})
                    disable_hooks = upgrade.get('no_hooks', False)
                    force = upgrade.get('force', False)
                    recreate_pods = upgrade.get('recreate_pods', False)

                    LOG.info("Checking Pre/Post Actions")
                    if upgrade:
                        upgrade_pre = upgrade.get('pre', {})
                        upgrade_post = upgrade.get('post', {})

                        if not self.disable_update_pre and upgrade_pre:
                            pre_actions = upgrade_pre

                        if not self.disable_update_post and upgrade_post:
                            post_actions = upgrade_post

                    try:
                        old_values = yaml.safe_load(old_values_string)
                    except yaml.YAMLError:
                        chart_desc = '{} (previously deployed)'.format(
                            old_chart.metadata.name)
                        raise armada_exceptions.\
                            InvalidOverrideValuesYamlException(chart_desc)

                    LOG.info('Checking for updates to chart release inputs.')
                    diff = self.get_diff(old_chart, old_values, new_chart,
                                         values)

                    if not diff:
                        LOG.info("Found no updates to chart release inputs")
                        continue

                    LOG.info("Found updates to chart release inputs")
                    LOG.debug("%s", diff)
                    msg['diff'].append({chart['release']: str(diff)})

                    # TODO(MarshM): Add tiller dry-run before upgrade and
                    # consider deadline impacts

                    # do actual update
                    timer = int(round(deadline - time.time()))
                    LOG.info('Beginning Upgrade, wait=%s, timeout=%ss',
                             this_chart_should_wait, timer)
                    tiller_result = self.tiller.update_release(
                        new_chart,
                        release_name,
                        namespace,
                        pre_actions=pre_actions,
                        post_actions=post_actions,
                        disable_hooks=disable_hooks,
                        values=yaml.safe_dump(values),
                        wait=this_chart_should_wait,
                        timeout=timer,
                        force=force,
                        recreate_pods=recreate_pods)

                    if this_chart_should_wait:
                        self._wait_until_ready(release_name, wait_labels,
                                               namespace, timer)

                    # Track namespace+labels touched by upgrade
                    ns_label_set.add((namespace, tuple(wait_labels.items())))

                    LOG.info('Upgrade completed with results from Tiller: %s',
                             tiller_result.__dict__)
                    msg['upgrade'].append(release_name)

                # process install
                else:
                    LOG.info("Installing release %s in namespace %s",
                             release_name, namespace)

                    timer = int(round(deadline - time.time()))
                    LOG.info('Beginning Install, wait=%s, timeout=%ss',
                             this_chart_should_wait, timer)
                    tiller_result = self.tiller.install_release(
                        new_chart,
                        release_name,
                        namespace,
                        values=yaml.safe_dump(values),
                        wait=this_chart_should_wait,
                        timeout=timer)

                    if this_chart_should_wait:
                        self._wait_until_ready(release_name, wait_labels,
                                               namespace, timer)

                    # Track namespace+labels touched by install
                    ns_label_set.add((namespace, tuple(wait_labels.items())))

                    LOG.info('Install completed with results from Tiller: %s',
                             tiller_result.__dict__)
                    msg['install'].append(release_name)

                # Keeping track of time remaining
                timer = int(round(deadline - time.time()))
                test_chart_args = (release_name, timer, test_cleanup)
                if test_this_chart:
                    # Sequenced ChartGroup should run tests after each Chart
                    if cg_sequenced:
                        LOG.info(
                            'Running sequenced test, timeout remaining: '
                            '%ss.', timer)
                        self._test_chart(*test_chart_args)

                    # Un-sequenced ChartGroup should run tests at the end
                    else:
                        tests_to_run.append(
                            functools.partial(self._test_chart,
                                              *test_chart_args))

            # End of Charts in ChartGroup
            LOG.info('All Charts applied in ChartGroup %s.', cg_name)

            # After all Charts are applied, we should wait for the entire
            # ChartGroup to become healthy by looking at the namespaces seen
            # TODO(MarshM): Need to determine a better timeout
            #               (not cg_max_timeout)
            if cg_max_timeout <= 0:
                cg_max_timeout = const.DEFAULT_CHART_TIMEOUT
            deadline = time.time() + cg_max_timeout
            for (ns, labels) in ns_label_set:
                labels_dict = dict(labels)
                timer = int(round(deadline - time.time()))
                LOG.info(
                    'Final ChartGroup wait for healthy namespace=%s, '
                    'labels=(%s), timeout remaining: %ss.', ns, labels_dict,
                    timer)
                if timer <= 0:
                    reason = ('Timeout expired waiting on namespace: %s, '
                              'labels: (%s)' % (ns, labels_dict))
                    LOG.error(reason)
                    raise armada_exceptions.ArmadaTimeoutException(reason)

                self._wait_until_ready(
                    release_name=None,
                    wait_labels=labels_dict,
                    namespace=ns,
                    timeout=timer)

            # After entire ChartGroup is healthy, run any pending tests
            for callback in tests_to_run:
                callback()

        self.post_flight_ops()

        if self.enable_chart_cleanup:
            self._chart_cleanup(
                prefix,
                self.manifest[const.KEYWORD_ARMADA][const.KEYWORD_GROUPS], msg)

        LOG.info('Done applying manifest.')
        return msg

    def post_flight_ops(self):
        '''
        Operations to run after deployment process has terminated
        '''
        LOG.info("Performing post-flight operations.")

        # Delete temp dirs used for deployment
        for cloned_dir in self.cloned_dirs:
            LOG.debug('Removing cloned temp directory: %s', cloned_dir)
            source.source_cleanup(cloned_dir)

    def _wait_until_ready(self, release_name, wait_labels, namespace, timeout):
        if self.dry_run:
            LOG.info(
                'Skipping wait during `dry-run`, would have waited on '
                'namespace=%s, labels=(%s) for %ss.', namespace, wait_labels,
                timeout)
            return

        self.tiller.k8s.wait_until_ready(
            release=release_name,
            labels=wait_labels,
            namespace=namespace,
            k8s_wait_attempts=self.k8s_wait_attempts,
            k8s_wait_attempt_sleep=self.k8s_wait_attempt_sleep,
            timeout=timeout)

    def _test_chart(self, release_name, timeout, cleanup):
        if self.dry_run:
            LOG.info(
                'Skipping test during `dry-run`, would have tested '
                'release=%s with timeout %ss.', release_name, timeout)
            return True

        if timeout <= 0:
            reason = ('Timeout expired before testing '
                      'release %s' % release_name)
            LOG.error(reason)
            raise armada_exceptions.ArmadaTimeoutException(reason)

        success = test_release_for_success(
            self.tiller, release_name, timeout=timeout, cleanup=cleanup)
        if success:
            LOG.info("Test passed for release: %s", release_name)
        else:
            LOG.info("Test failed for release: %s", release_name)
            raise tiller_exceptions.TestFailedException(release_name)

    def _chart_cleanup(self, prefix, charts, msg):
        LOG.info('Processing chart cleanup to remove unspecified releases.')

        valid_releases = []
        for gchart in charts:
            for chart in gchart.get(const.KEYWORD_CHARTS, []):
                valid_releases.append(
                    release_prefixer(prefix,
                                     chart.get('chart', {}).get('release')))

        actual_releases = [x.name for x in self.tiller.list_releases()]
        release_diff = list(set(actual_releases) - set(valid_releases))

        for release in release_diff:
            if release.startswith(prefix):
                LOG.info('Purging release %s as part of chart cleanup.',
                         release)
                self.tiller.uninstall_release(release)
                msg['purge'].append(release)

    def get_diff(self, old_chart, old_values, new_chart, values):
        return ReleaseDiff(old_chart, old_values, new_chart, values).get_diff()
