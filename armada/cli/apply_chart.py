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

import click
from oslo_config import cfg
import prometheus_client
import yaml

from armada.cli import CliAction
from armada.exceptions.source_exceptions import InvalidPathException
from armada.handlers import metrics
from armada.handlers.chart_deploy import ChartDeploy
from armada.handlers.chart_download import ChartDownload
from armada.handlers.document import ReferenceResolver
from armada.handlers.lock import lock_and_thread
from armada.handlers.manifest import Chart
from armada.handlers.tiller import Tiller

CONF = cfg.CONF


@click.group()
def apply_chart():
    """ Apply chart to cluster

    """


DESC = """
This command installs and updates an Armada chart.

[LOCATION] must be a relative path to Armada Chart or a reference
to an Armada Chart kubernetes CR which has the same format, except as
noted in the v2 document authoring documentation.

To install or upgrade a chart, run:

      \b
      $ armada apply_chart --release-prefix=armada my-chart.yaml
      $ armada apply_chart --release-prefix=armada \
      kube:armadacharts/my-namespace/my-chart
"""

SHORT_DESC = "Command deploys a chart."


@apply_chart.command(name='apply_chart', help=DESC, short_help=SHORT_DESC)
@click.argument('location')
@click.option(
    '--release-prefix',
    help="Prefix to prepend to chart release name.",
    required=True)
@click.option(
    '--disable-update-post',
    help="Disable post-update Tiller operations.",
    is_flag=True)
@click.option(
    '--disable-update-pre',
    help="Disable pre-update Tiller operations.",
    is_flag=True)
@click.option(
    '--metrics-output',
    help=(
        "Output path for prometheus metric data, should end in .prom. By "
        "default, no metric data is output."),
    default=None)
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
    '--wait',
    help=(
        "Force Tiller to wait until the chart is deployed, "
        "rather than using the chart's specified wait policy. "
        "This is equivalent to sequenced chartgroups."),
    is_flag=True)
@click.option(
    '--target-chart',
    help=(
        "The target chart to deploy. Required for specifying "
        "which chart to deploy when multiple are available."),
    default=None)
@click.option('--bearer-token', help="User Bearer token", default=None)
@click.option('--debug', help="Enable debug logging.", is_flag=True)
@click.pass_context
def apply_chart(
        ctx, location, release_prefix, disable_update_post, disable_update_pre,
        metrics_output, tiller_host, tiller_port, tiller_namespace, timeout,
        wait, target_chart, bearer_token, debug):
    CONF.debug = debug
    ApplyChart(
        ctx, location, release_prefix, disable_update_post, disable_update_pre,
        metrics_output, tiller_host, tiller_port, tiller_namespace, timeout,
        wait, target_chart, bearer_token).safe_invoke()


class ApplyChart(CliAction):
    def __init__(
            self, ctx, location, release_prefix, disable_update_post,
            disable_update_pre, metrics_output, tiller_host, tiller_port,
            tiller_namespace, timeout, wait, target_chart, bearer_token):
        super(ApplyChart, self).__init__()
        self.ctx = ctx
        self.release_prefix = release_prefix
        # Filename can also be a URL reference
        self.location = location
        self.disable_update_post = disable_update_post
        self.disable_update_pre = disable_update_pre
        self.metrics_output = metrics_output
        self.tiller_host = tiller_host
        self.tiller_port = tiller_port
        self.tiller_namespace = tiller_namespace
        self.timeout = timeout
        self.target_chart = target_chart
        self.bearer_token = bearer_token

    def output(self, resp):
        for result in resp:
            if not resp[result] and not result == 'diff':
                self.logger.info('Did not perform chart %s(s)', result)
            elif result == 'diff' and not resp[result]:
                self.logger.info('No release changes detected')

            ch = resp[result]
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
        with Tiller(tiller_host=self.tiller_host, tiller_port=self.tiller_port,
                    tiller_namespace=self.tiller_namespace,
                    bearer_token=self.bearer_token) as tiller:

            try:
                doc_data = ReferenceResolver.resolve_reference(
                    self.location, k8s=tiller.k8s)
                documents = list()
                for d in doc_data:
                    documents.extend(list(yaml.safe_load_all(d.decode())))
            except InvalidPathException as ex:
                self.logger.error(str(ex))
                return
            except yaml.YAMLError as yex:
                self.logger.error("Invalid YAML found: %s" % str(yex))
                return

            try:
                resp = self.handle(documents, tiller)
                self.output(resp)
            finally:
                if self.metrics_output:
                    path = self.metrics_output
                    self.logger.info(
                        'Storing metrics output in path: {}'.format(path))
                    prometheus_client.write_to_textfile(path, metrics.REGISTRY)

    def handle(self, documents, tiller):
        chart = Chart(documents, target_chart=self.target_chart).get_chart()

        lock_name = 'chart-{}'.format(chart['metadata']['name'])

        @lock_and_thread(lock_name)
        def _handle():
            chart_download = ChartDownload()
            try:
                chart_download.get_chart(chart)
                chart_deploy = ChartDeploy(
                    None, self.disable_update_pre, self.disable_update_post, 1,
                    1, self.timeout, tiller)

                # TODO: Only get release with matching name.
                known_releases = tiller.list_releases()

                return chart_deploy.execute(
                    chart, None, self.release_prefix, known_releases, 1)
            finally:
                chart_download.cleanup()

        return _handle()
