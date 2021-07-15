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
import prometheus_client
import yaml

from armada.cli import CliAction
from armada.exceptions.source_exceptions import InvalidPathException
from armada.handlers import metrics
from armada.handlers.armada import Armada
from armada.handlers.document import ReferenceResolver
from armada.handlers.lock import lock_and_thread
from armada.handlers.helm import Helm

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
    https://docs.airshipit.org/armada/operations/

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
    '--enable-chart-cleanup', help="Clean up unmanaged charts.", is_flag=True)
@click.option(
    '--metrics-output',
    help=(
        "Output path for prometheus metric data, should end in .prom. By "
        "default, no metric data is output."),
    default=None)
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
        "rather than using each charts specified wait policy. "
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
        ctx, locations, api, disable_update_post, disable_update_pre,
        enable_chart_cleanup, metrics_output, use_doc_ref, set, timeout,
        values, wait, target_manifest, bearer_token, debug):
    CONF.debug = debug
    ApplyManifest(
        ctx, locations, api, disable_update_post, disable_update_pre,
        enable_chart_cleanup, metrics_output, use_doc_ref, set, timeout,
        values, wait, target_manifest, bearer_token).safe_invoke()


class ApplyManifest(CliAction):
    def __init__(
            self, ctx, locations, api, disable_update_post, disable_update_pre,
            enable_chart_cleanup, metrics_output, use_doc_ref, set, timeout,
            values, wait, target_manifest, bearer_token):
        super(ApplyManifest, self).__init__()
        self.ctx = ctx
        # Filename can also be a URL reference
        self.locations = locations
        self.api = api
        self.disable_update_post = disable_update_post
        self.disable_update_pre = disable_update_pre
        self.enable_chart_cleanup = enable_chart_cleanup
        self.metrics_output = metrics_output
        self.use_doc_ref = use_doc_ref
        self.set = set
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
            with Helm(bearer_token=self.bearer_token) as helm:

                try:
                    resp = self.handle(documents, helm)
                    self.output(resp)
                finally:
                    if self.metrics_output:
                        path = self.metrics_output
                        self.logger.info(
                            'Storing metrics output in path: {}'.format(path))
                        prometheus_client.write_to_textfile(
                            path, metrics.REGISTRY)
        else:
            if len(self.values) > 0:
                self.logger.error(
                    "Cannot specify local values files when using the API.")
                return

            query = {
                'disable_update_post': self.disable_update_post,
                'disable_update_pre': self.disable_update_pre,
                'enable_chart_cleanup': self.enable_chart_cleanup,
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
    def handle(self, documents, helm):
        armada = Armada(
            documents,
            disable_update_pre=self.disable_update_pre,
            disable_update_post=self.disable_update_post,
            enable_chart_cleanup=self.enable_chart_cleanup,
            set_ovr=self.set,
            force_wait=self.wait,
            timeout=self.timeout,
            helm=helm,
            values=self.values,
            target_manifest=self.target_manifest)
        return armada.sync()
