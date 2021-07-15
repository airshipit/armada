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

import click
from oslo_config import cfg
import yaml

from armada.cli import CliAction
from armada import const
from armada.handlers.lock import lock_and_thread
from armada.handlers.manifest import Manifest
from armada.handlers.test import Test
from armada.handlers.helm import Helm, HelmReleaseId
from armada.utils.release import release_prefixer

CONF = cfg.CONF


@click.group()
def test():
    """ Test Manifest Charts

    """


DESC = """
This command tests deployed charts.

The test command will run the release chart tests either via a the manifest or
by targeting a release.

To test Armada deployed releases:

    $ armada test --file examples/simple.yaml

To test release:

    $ armada test --namespace blog --release blog-1

"""

SHORT_DESC = "Command tests releases."


@test.command(name='test', help=DESC, short_help=SHORT_DESC)
@click.option('--file', help="Armada manifest.", type=str)
@click.option('--namespace', help="Helm release namespace.", type=str)
@click.option('--release', help="Helm release.", type=str)
@click.option(
    '--target-manifest',
    help=(
        "The target manifest to run. Required for specifying "
        "which manifest to run when multiple are available."),
    default=None)
@click.option(
    '--enable-all',
    help=(
        "Run all tests for all releases regardless of any disabled chart "
        "tests."),
    is_flag=True,
    default=False)
@click.option('--debug', help="Enable debug logging.", is_flag=True)
@click.pass_context
def test_charts(
        ctx, file, namespace, release, target_manifest, enable_all, debug):
    CONF.debug = debug
    TestChartManifest(
        ctx, file, namespace, release, target_manifest,
        enable_all).safe_invoke()


class TestChartManifest(CliAction):
    def __init__(
            self, ctx, file, namespace, release, target_manifest, enable_all):

        super(TestChartManifest, self).__init__()
        self.ctx = ctx
        self.file = file
        self.namespace = namespace
        self.release = release
        self.target_manifest = target_manifest
        self.enable_all = enable_all

    def invoke(self):
        with Helm() as helm:

            self.handle(helm)

    @lock_and_thread()
    def handle(self, helm):
        release_ids = helm.list_release_ids()

        if self.release:
            if not self.ctx.obj.get('api', False):
                release_id = HelmReleaseId(self.namespace, self.release)
                test_handler = Test({}, release_id, helm)
                test_handler.test_release_for_success()
            else:
                client = self.ctx.obj.get('CLIENT')
                resp = client.get_test_release(release=self.release)

                self.logger.info(resp.get('result'))
                self.logger.info(resp.get('message'))

        if self.file:
            if not self.ctx.obj.get('api', False):
                documents = list(yaml.safe_load_all(open(self.file).read()))
                armada_obj = Manifest(
                    documents,
                    target_manifest=self.target_manifest).get_manifest()
                prefix = armada_obj.get(const.KEYWORD_DATA).get(
                    const.KEYWORD_PREFIX)

                for group in armada_obj.get(const.KEYWORD_DATA).get(
                        const.KEYWORD_GROUPS):
                    for ch in group.get(const.KEYWORD_CHARTS):
                        chart = ch['chart']

                        release_id = HelmReleaseId(
                            chart['namespace'],
                            release_prefixer(prefix, chart['release']))
                        if release_id in release_ids:
                            test_handler = Test(
                                chart,
                                release_id,
                                helm,
                                enable_all=self.enable_all)

                            if test_handler.test_enabled:
                                test_handler.test_release_for_success()
                        else:
                            self.logger.info(
                                'Release %s not found - SKIPPING', release_id)
            else:
                client = self.ctx.obj.get('CLIENT')

                with open(self.filename, 'r') as f:
                    resp = client.get_test_manifest(manifest=f.read())
                    for test in resp.get('tests'):
                        self.logger.info('Test State: %s', test)
                        for item in test.get('tests').get(test):
                            self.logger.info(item)

                    self.logger.info(resp)
