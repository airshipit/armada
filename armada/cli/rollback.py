# Copyright 2018 The Armada Authors.
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

from armada.cli import CliAction
from armada.handlers.lock import lock_and_thread
from armada.handlers.tiller import Tiller

CONF = cfg.CONF


@click.group()
def rollback():
    """ Rollback a helm release

    """


DESC = """
This command performs a rollback on the specified release.

To rollback a release, run:

    \b
    $ armada rollback --release my_release

"""

SHORT_DESC = "Command performs a release rollback."


@rollback.command(name='rollback', help=DESC, short_help=SHORT_DESC)
@click.option('--release', help="Release to rollback.", type=str)
@click.option(
    '--version',
    help="Version of release to rollback to. 0 represents the "
    "previous release",
    type=int,
    default=0)
@click.option('--tiller-host', help="Tiller host IP.", default=None)
@click.option(
    '--tiller-port', help="Tiller host port.", type=int, default=None)
@click.option(
    '--tiller-namespace',
    '-tn',
    help="Tiller namespace.",
    type=str,
    default=None)
@click.option(
    '--timeout',
    help="Specifies time to wait for rollback to complete.",
    type=int,
    default=0)
@click.option(
    '--wait',
    help=("Wait until rollback is complete before returning."),
    is_flag=True)
@click.option(
    '--force',
    help=("Force resource update through delete/recreate if"
          " needed."),
    is_flag=True)
@click.option(
    '--recreate-pods',
    help=("Restarts pods for the resource if applicable."),
    is_flag=True)
@click.option('--bearer-token', help=("User bearer token."), default=None)
@click.option('--debug', help="Enable debug logging.", is_flag=True)
@click.pass_context
def rollback_charts(
        ctx, release, version, tiller_host, tiller_port, tiller_namespace,
        timeout, wait, force, recreate_pods, bearer_token, debug):
    CONF.debug = debug
    Rollback(
        ctx, release, version, tiller_host, tiller_port, tiller_namespace,
        timeout, wait, force, recreate_pods, bearer_token).safe_invoke()


class Rollback(CliAction):
    def __init__(
            self, ctx, release, version, tiller_host, tiller_port,
            tiller_namespace, timeout, wait, force, recreate_pods,
            bearer_token):
        super(Rollback, self).__init__()
        self.ctx = ctx
        self.release = release
        self.version = version
        self.tiller_host = tiller_host
        self.tiller_port = tiller_port
        self.tiller_namespace = tiller_namespace
        self.timeout = timeout
        self.wait = wait
        self.force = force
        self.recreate_pods = recreate_pods
        self.bearer_token = bearer_token

    def invoke(self):
        with Tiller(tiller_host=self.tiller_host, tiller_port=self.tiller_port,
                    tiller_namespace=self.tiller_namespace,
                    bearer_token=self.bearer_token) as tiller:

            response = self.handle(tiller)

            self.output(response)

    @lock_and_thread()
    def handle(self, tiller):
        return tiller.rollback_release(
            self.release,
            self.version,
            wait=self.wait,
            timeout=self.timeout,
            force=self.force,
            recreate_pods=self.recreate_pods)

    def output(self, response):
        self.logger.info('Rollback of %s complete.', self.release)
