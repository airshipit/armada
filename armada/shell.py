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

from urllib.parse import urlparse

import click
from oslo_config import cfg
from oslo_log import log

from armada.cli.apply import apply_create
from armada.cli.test import test_charts
from armada.cli.validate import validate_manifest
from armada.common.client import ArmadaClient
from armada.common.session import ArmadaSession

CONF = cfg.CONF


@click.group()
@click.option('--debug', help="Enable debug logging", is_flag=True)
@click.option(
    '--api/--no-api',
    help="Execute service endpoints. (requires url option)",
    default=False)
@click.option(
    '--url', help="Armada Service Endpoint", envvar='HOST', default=None)
@click.option(
    '--token', help="Keystone Service Token", envvar='TOKEN', default=None)
@click.pass_context
def main(ctx, debug, api, url, token):
    """
    Multi Helm Chart Deployment Manager

    Common actions from this point include:

    \b
    $ armada apply
    $ armada test
    $ armada validate

    Environment:

        \b
        $TOKEN set auth token
        $HOST  set armada service host endpoint
    """

    if not ctx.obj:
        ctx.obj = {}

    if api:
        if not url or not token:
            raise click.ClickException(
                'When api option is enabled user needs to pass url and token')
        else:
            ctx.obj['api'] = api
            parsed_url = urlparse(url)
            ctx.obj['CLIENT'] = ArmadaClient(
                ArmadaSession(
                    host=parsed_url.netloc,
                    scheme=parsed_url.scheme,
                    token=token))

    if debug:
        CONF.debug = debug

    log.set_defaults(default_log_levels=CONF.default_log_levels)
    log.setup(CONF, 'armada')


main.add_command(apply_create)
main.add_command(test_charts)
main.add_command(validate_manifest)
