# Copyright 2021 The Armada Authors.
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

from base64 import b64decode
import gzip
import io
import json as JSON
import subprocess  # nosec
import tempfile
from typing import NamedTuple

from oslo_config import cfg
from oslo_log import log as logging
import yaml

from armada.exceptions.helm_exceptions import HelmCommandException
from armada.handlers.k8s import K8s

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

DEFAULT_HELM_TIMEOUT = 300

STATUS_DEPLOYED = 'deployed'
STATUS_FAILED = 'failed'


class Helm(object):
    '''
    Helm CLI handler
    '''
    def __init__(self, bearer_token=None):
        self.bearer_token = bearer_token

        # init k8s connectivity
        self.k8s = K8s(bearer_token=self.bearer_token)

    def _run(self, sub_command, args, json=True, timeout=None):
        if isinstance(sub_command, str):
            sub_command = [sub_command]
        command = ['helm'] + sub_command
        if json:
            command = command + ['--output', 'json']
        command = command + args
        LOG.info('Running command=%s', command)
        try:
            result = subprocess.run(  # nosec
                command,
                check=True,
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout)
        except subprocess.CalledProcessError as e:
            raise HelmCommandException(e)

        if json:
            return JSON.loads(result.stdout)
        return result.stdout

    def list_releases(self):
        return self._run(
            'ls', ['--all-namespaces', '--all'], timeout=DEFAULT_HELM_TIMEOUT)

    def list_release_ids(self):
        return [
            HelmReleaseId(r['namespace'], r['name'])
            for r in self.list_releases()
        ]

    def install_release(
            self,
            chart,
            release_id,
            values=None,
            wait=False,
            dry_run=False,
            timeout=None):
        timeout = self._check_timeout(wait, timeout)

        args = [
            release_id.name,
            chart,
            '--namespace',
            release_id.namespace,
            '--create-namespace',
            '--timeout',
            '{}s'.format(timeout),
            # TODO: (also for upgrade_release) This is for backward
            # compatibility with helm 2 based Armada. We may want to consider
            # making this configurable and/or defaulting to enabling.
            '--disable-openapi-validation'
        ]
        if wait:
            args = args + ['--wait']
        if dry_run:
            args = args + ['--dry-run']

        with _TempValuesFile(values) as values_file:
            args = args + ['--values', values_file.file.name]
            return self._run('install', args, timeout=timeout)

    def upgrade_release(
            self,
            chart,
            release_id,
            disable_hooks=False,
            values=None,
            wait=False,
            dry_run=False,
            timeout=None,
            force=False):
        timeout = self._check_timeout(wait, timeout)

        args = [
            release_id.name, chart, '--namespace', release_id.namespace,
            '--timeout', '{}s'.format(timeout), '--disable-openapi-validation'
        ]
        if disable_hooks:
            args = args + ['--no-hooks']
        if force:
            args = args + ['--force']
        if wait:
            args = args + ['--wait']
        if dry_run:
            args = args + ['--dry-run']

        with _TempValuesFile(values) as values_file:
            args = args + ['--values', values_file.file.name]
            return self._run('upgrade', args, timeout=timeout)

    def test_release(self, release_id, timeout=DEFAULT_HELM_TIMEOUT):
        return self._run(
            'test', [
                release_id.name, '--namespace', release_id.namespace,
                '--timeout', '{}s'.format(timeout)
            ],
            json=False,
            timeout=timeout)

    def release_status(self, release_id, version=None):
        args = [release_id.name, '--namespace', release_id.namespace]
        if version is not None:
            args = args + ['--version', version]

        try:
            return self._run('status', args)
        except HelmCommandException as e:
            stderr = e.called_process_error.stderr.strip()
            if 'Error: release: not found' == stderr:
                return None
            raise

    # Ideally we could just use `helm status`, but this is missing the
    # chart metadata which we use for release diffing:
    #   https://github.com/helm/helm/issues/9968
    #
    # So instead we access the helm release metadata secret directly
    # as describe here:
    #   https://gist.github.com/DzeryCZ/c4adf39d4a1a99ae6e594a183628eaee
    def release_metadata(self, release_id, version=None):
        if version is None:
            # determine latest version
            release = self.release_status(release_id)
            if release is None:
                return None
            version = release['version']
        secret_name = 'sh.helm.release.v1.{}.v{}'.format(
            release_id.name, version)
        secret_namespace = release_id.namespace
        secret = self.k8s.read_namespaced_secret(secret_name, secret_namespace)
        raw_data = secret.data['release']
        k8s_data = b64decode(raw_data)
        helm_data = b64decode(k8s_data)
        helm_data_file_handle = io.BytesIO(helm_data)
        helm_json = gzip.GzipFile(fileobj=helm_data_file_handle).read()
        return JSON.loads(helm_json)

    def uninstall_release(
            self,
            release_id,
            disable_hooks=False,
            purge=True,
            timeout=DEFAULT_HELM_TIMEOUT):

        args = [release_id.name, '--namespace', release_id.namespace]
        if not purge:
            args = args + ['--keep-history']
        if disable_hooks:
            args = args + ['--no-hooks']
        return self._run('uninstall', args, json=False, timeout=timeout)

    def show_chart(self, chart_dir):

        output = self._run(['show', 'chart'], [chart_dir], json=False)
        return yaml.safe_load(output)

    def _check_timeout(self, wait, timeout):
        if timeout is None or timeout <= 0:
            timeout = DEFAULT_HELM_TIMEOUT
            if wait:
                LOG.warn(
                    'Helm timeout is invalid or unspecified, '
                    'using default %ss.', timeout)
        return timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class _TempValuesFile():
    def __init__(self, values):
        self.values = values
        self.file = tempfile.NamedTemporaryFile(
            mode='w', prefix='armada_values', suffix='.yaml')

    def __enter__(self):
        self.file.__enter__()
        values_content = yaml.safe_dump(self.values)
        self.file.write(values_content)
        self.file.flush()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self.file.__exit__(exc_type, exc_value, traceback)


class HelmReleaseId(NamedTuple('HelmReleaseId', [('namespace', str),
                                                 ('name', str)])):
    """Represents a helm release id."""
    __slots__ = ()

    def __str__(self):
        return '{}/{}'.format(self.namespace, self.name)
