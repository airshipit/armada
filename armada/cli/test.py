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
from armada.handlers.tiller import Tiller
from armada.utils.release import release_prefixer

CONF = cfg.CONF


@click.group()
def test():
    """ Test Manifest Charts

    """


DESC = """
This command tests deployed charts.

The tiller command uses flags to obtain information from Tiller services.
The test command will run the release chart tests either via a the manifest or
by targeting a release.

To test Armada deployed releases:

    $ armada test --file examples/simple.yaml

To test release:

    $ armada test --release blog-1

"""

SHORT_DESC = "Command tests releases."


@test.command(name='test', help=DESC, short_help=SHORT_DESC)
@click.option('--file', help="Armada manifest.", type=str)
@click.option('--release', help="Helm release.", type=str)
@click.option('--tiller-host', help="Tiller host IP.", default=None)
@click.option(
    '--tiller-port', help="Tiller host port.", type=int, default=None)
@click.option(
    '--tiller-namespace',
    '-tn',
    help="Tiller Namespace.",
    type=str,
    default=None)
@click.option(
    '--target-manifest',
    help=(
        "The target manifest to run. Required for specifying "
        "which manifest to run when multiple are available."),
    default=None)
@click.option(
    '--cleanup',
    help=("Delete test pods upon completion."),
    is_flag=True,
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
        ctx, file, release, tiller_host, tiller_port, tiller_namespace,
        target_manifest, cleanup, enable_all, debug):
    CONF.debug = debug
    TestChartManifest(
        ctx, file, release, tiller_host, tiller_port, tiller_namespace,
        target_manifest, cleanup, enable_all).safe_invoke()


class TestChartManifest(CliAction):
    def __init__(
            self, ctx, file, release, tiller_host, tiller_port,
            tiller_namespace, target_manifest, cleanup, enable_all):

        super(TestChartManifest, self).__init__()
        self.ctx = ctx
        self.file = file
        self.release = release
        self.tiller_host = tiller_host
        self.tiller_port = tiller_port
        self.tiller_namespace = tiller_namespace
        self.target_manifest = target_manifest
        self.cleanup = cleanup
        self.enable_all = enable_all

    def invoke(self):
        with Tiller(tiller_host=self.tiller_host, tiller_port=self.tiller_port,
                    tiller_namespace=self.tiller_namespace) as tiller:

            self.handle(tiller)

    @lock_and_thread()
    def handle(self, tiller):
        known_release_names = [release[0] for release in tiller.list_charts()]

        if self.release:
            if not self.ctx.obj.get('api', False):
                test_handler = Test(
                    {}, self.release, tiller, cleanup=self.cleanup)
                test_handler.test_release_for_success()
            else:
                client = self.ctx.obj.get('CLIENT')
                query = {
                    'tiller_host': self.tiller_host,
                    'tiller_port': self.tiller_port,
                    'tiller_namespace': self.tiller_namespace
                }
                resp = client.get_test_release(
                    release=self.release, query=query)

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

                        release_name = release_prefixer(
                            prefix, chart.get('release'))
                        if release_name in known_release_names:
                            test_handler = Test(
                                chart,
                                release_name,
                                tiller,
                                cleanup=self.cleanup,
                                enable_all=self.enable_all)

                            if test_handler.test_enabled:
                                test_handler.test_release_for_success()
                        else:
                            self.logger.info(
                                'Release %s not found - SKIPPING',
                                release_name)
            else:
                client = self.ctx.obj.get('CLIENT')
                query = {
                    'tiller_host': self.tiller_host,
                    'tiller_port': self.tiller_port,
                    'tiller_namespace': self.tiller_namespace
                }

                with open(self.filename, 'r') as f:
                    resp = client.get_test_manifest(
                        manifest=f.read(), query=query)
                    for test in resp.get('tests'):
                        self.logger.info('Test State: %s', test)
                        for item in test.get('tests').get(test):
                            self.logger.info(item)

                    self.logger.info(resp)
