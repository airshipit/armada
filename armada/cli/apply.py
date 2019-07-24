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
from armada.exceptions.source_exceptions import InvalidPathException
from armada.handlers.armada import Armada
from armada.handlers.document import ReferenceResolver
from armada.handlers.lock import lock_and_thread
from armada.handlers.tiller import Tiller

CONF = cfg.CONF


@click.group()
def apply():
    """ Apply manifest to cluster

    """


DESC = """
This command installs and updates charts defined in Armada manifest.

The apply argument must be relative path to Armada Manifest. Executing apply
command once will install all charts defined in manifest. Re-executing apply
command will execute upgrade.

To see how to create an Armada manifest:
    https://airship-armada.readthedocs.io/en/latest/operations/

To install or upgrade charts, run:

    \b
    $ armada apply examples/simple.yaml

To override a specific value in a Manifest, run:

    \b
    $ armada apply examples/simple.yaml \
--set manifest:simple-armada:release="wordpress"

Or to override several values in a Manifest, reference a values.yaml-formatted
file:

    \b
    $ armada apply examples/simple.yaml \
--values examples/simple-ovr-values.yaml

"""

SHORT_DESC = "Command installs manifest charts."


@apply.command(name='apply', help=DESC, short_help=SHORT_DESC)
@click.argument('locations', nargs=-1)
@click.option('--api', help="Contacts service endpoint.", is_flag=True)
@click.option(
    '--disable-update-post',
    help="Disable post-update Tiller operations.",
    is_flag=True)
@click.option(
    '--disable-update-pre',
    help="Disable pre-update Tiller operations.",
    is_flag=True)
@click.option(
    '--dry-run', help="Run charts without installing them.", is_flag=True)
@click.option(
    '--enable-chart-cleanup', help="Clean up unmanaged charts.", is_flag=True)
@click.option(
    '--use-doc-ref', help="Use armada manifest file reference.", is_flag=True)
@click.option(
    '--set',
    help=(
        "Use to override Armada Manifest values. Accepts "
        "overrides that adhere to the format "
        "<path>:<to>:<property>=<value> to specify a primitive or "
        "<path>:<to>:<property>=<value1>,...,<valueN> to specify "
        "a list of values."),
    multiple=True,
    type=str,
    default=[])
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
    help="Specifies time to wait for each chart to fully "
    "finish deploying.",
    type=int)
@click.option(
    '--values',
    '-f',
    help=(
        "Use to override multiple Armada Manifest values by "
        "reading overrides from a values.yaml-type file."),
    multiple=True,
    type=str,
    default=[])
@click.option(
    '--wait',
    help=(
        "Force Tiller to wait until all charts are deployed, "
        "rather than using each chart's specified wait policy. "
        "This is equivalent to sequenced chartgroups."),
    is_flag=True)
@click.option(
    '--target-manifest',
    help=(
        "The target manifest to run. Required for specifying "
        "which manifest to run when multiple are available."),
    default=None)
@click.option('--bearer-token', help="User Bearer token", default=None)
@click.option('--debug', help="Enable debug logging.", is_flag=True)
@click.pass_context
def apply_create(
        ctx, locations, api, disable_update_post, disable_update_pre, dry_run,
        enable_chart_cleanup, use_doc_ref, set, tiller_host, tiller_port,
        tiller_namespace, timeout, values, wait, target_manifest, bearer_token,
        debug):
    CONF.debug = debug
    ApplyManifest(
        ctx, locations, api, disable_update_post, disable_update_pre, dry_run,
        enable_chart_cleanup, use_doc_ref, set, tiller_host, tiller_port,
        tiller_namespace, timeout, values, wait, target_manifest,
        bearer_token).safe_invoke()


class ApplyManifest(CliAction):
    def __init__(
            self, ctx, locations, api, disable_update_post, disable_update_pre,
            dry_run, enable_chart_cleanup, use_doc_ref, set, tiller_host,
            tiller_port, tiller_namespace, timeout, values, wait,
            target_manifest, bearer_token):
        super(ApplyManifest, self).__init__()
        self.ctx = ctx
        # Filename can also be a URL reference
        self.locations = locations
        self.api = api
        self.disable_update_post = disable_update_post
        self.disable_update_pre = disable_update_pre
        self.dry_run = dry_run
        self.enable_chart_cleanup = enable_chart_cleanup
        self.use_doc_ref = use_doc_ref
        self.set = set
        self.tiller_host = tiller_host
        self.tiller_port = tiller_port
        self.tiller_namespace = tiller_namespace
        self.timeout = timeout
        self.values = values
        self.wait = wait
        self.target_manifest = target_manifest
        self.bearer_token = bearer_token

    def output(self, resp):
        for result in resp:
            if not resp[result] and not result == 'diff':
                self.logger.info('Did not perform chart %s(s)', result)
            elif result == 'diff' and not resp[result]:
                self.logger.info('No release changes detected')

            for ch in resp[result]:
                if not result == 'diff':
                    msg = 'Chart {} took action: {}'.format(ch, result)
                    if result == 'protected':
                        msg += ' and requires operator attention.'
                    elif result == 'purge':
                        msg += ' before install/upgrade.'
                    self.logger.info(msg)
                else:
                    self.logger.info('Chart/values diff: %s', ch)

    def invoke(self):
        try:
            doc_data = ReferenceResolver.resolve_reference(self.locations)
            documents = list()
            for d in doc_data:
                documents.extend(list(yaml.safe_load_all(d.decode())))
        except InvalidPathException as ex:
            self.logger.error(str(ex))
            return
        except yaml.YAMLError as yex:
            self.logger.error("Invalid YAML found: %s" % str(yex))
            return

        if not self.ctx.obj.get('api', False):
            with Tiller(tiller_host=self.tiller_host,
                        tiller_port=self.tiller_port,
                        tiller_namespace=self.tiller_namespace,
                        bearer_token=self.bearer_token,
                        dry_run=self.dry_run) as tiller:

                resp = self.handle(documents, tiller)
                self.output(resp)
        else:
            if len(self.values) > 0:
                self.logger.error(
                    "Cannot specify local values files when using the API.")
                return

            query = {
                'disable_update_post': self.disable_update_post,
                'disable_update_pre': self.disable_update_pre,
                'dry_run': self.dry_run,
                'enable_chart_cleanup': self.enable_chart_cleanup,
                'tiller_host': self.tiller_host,
                'tiller_port': self.tiller_port,
                'tiller_namespace': self.tiller_namespace,
                'timeout': self.timeout,
                'wait': self.wait
            }

            client = self.ctx.obj.get('CLIENT')
            if self.use_doc_ref:
                resp = client.post_apply(
                    manifest_ref=self.locations, set=self.set, query=query)
            else:
                resp = client.post_apply(
                    manifest=documents, set=self.set, query=query)
            self.output(resp.get('message'))

    @lock_and_thread()
    def handle(self, documents, tiller):
        armada = Armada(
            documents,
            disable_update_pre=self.disable_update_pre,
            disable_update_post=self.disable_update_post,
            enable_chart_cleanup=self.enable_chart_cleanup,
            dry_run=self.dry_run,
            set_ovr=self.set,
            force_wait=self.wait,
            timeout=self.timeout,
            tiller=tiller,
            values=self.values,
            target_manifest=self.target_manifest)
        return armada.sync()
