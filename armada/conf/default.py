# Copyright 2017 The Armada Authors.
#
# Licensed under the Apache License, Version 2.0 (the 'License'));
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from keystoneauth1 import loading as ks_loading
from oslo_config import cfg

from armada.conf import utils

default_options = [
    cfg.ListOpt(
        'armada_apply_roles',
        default=['admin'],
        help=utils.fmt('IDs of approved API access roles.')),
    cfg.StrOpt(
        'auth_url',
        default='http://0.0.0.0/v3',
        help=utils.fmt('The default Keystone authentication url.')),
    cfg.StrOpt(
        'certs',
        default=None,
        help=utils.fmt(
            """
Absolute path to the certificate file to use for chart registries
""")),
    cfg.StrOpt(
        'kubernetes_config_path',
        default='/home/user/.kube/',
        help=utils.fmt('Path to Kubernetes configurations.')),
    cfg.BoolOpt(
        'middleware',
        default=True,
        help=utils.fmt(
            """
Enables or disables Keystone authentication middleware.
""")),
    cfg.StrOpt(
        'project_domain_name',
        default='default',
        help=utils.fmt(
            """
The Keystone project domain name used for authentication.
""")),
    cfg.StrOpt(
        'project_name',
        default='admin',
        help=utils.fmt('The Keystone project name used for authentication.')),

    # TODO(fmontei): Add support for multiple SSH keys, not just one site-wide
    # one.
    cfg.StrOpt(
        'ssh_key_path',
        default='/home/user/.ssh/',
        help=utils.fmt(
            """Optional path to an SSH private key used for
authenticating against a Git source repository. The path must be an absolute
path to the private key that includes the name of the key itself.""")),
    cfg.IntOpt(
        'lock_acquire_timeout',
        default=60,
        min=0,
        help=utils.fmt(
            """Time in seconds of how long armada will attempt to
        acquire a lock before an exception is raised""")),
    cfg.IntOpt(
        'lock_acquire_delay',
        default=5,
        min=0,
        help=utils.fmt(
            """Time in seconds of how long to wait between attempts
    to acquire a lock""")),
    cfg.IntOpt(
        'lock_update_interval',
        default=60,
        min=0,
        help=utils.fmt(
            """Time in seconds of how often armada will update the
        lock while it is continuing to do work""")),
    cfg.IntOpt(
        'lock_expiration',
        default=600,
        min=0,
        help=utils.fmt(
            """Time in seconds of how much time needs to pass since
        the last update of an existing lock before armada forcibly removes it
        and tries to acquire its own lock""")),
    cfg.BoolOpt(
        'enable_operator',
        default=False,
        help=utils.fmt(
            """Determines whether the operator has to be enabled
        to apply charts instead of armada-api itself""")),
    cfg.BoolOpt(
        'go_wait',
        default=False,
        help=utils.fmt(
            """Determines whether the wait process has to be done
        via armada-go using client-go library""")),
]


def register_opts(conf):
    conf.register_opts(default_options)
    ks_loading.register_auth_conf_options(conf, group='keystone_authtoken')


def list_opts():
    return {
        'DEFAULT': default_options,
        'keystone_authtoken': (
            ks_loading.get_session_conf_options()
            + ks_loading.get_auth_common_conf_options()
            + ks_loading.get_auth_plugin_conf_options('password')
            + ks_loading.get_auth_plugin_conf_options('v3password'))
    }
