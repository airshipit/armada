# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import functools

from oslo_config import cfg
from oslo_log import log as logging
from oslo_policy import policy
from oslo_utils import excutils

from armada.common import policies
from armada.exceptions import base_exception as exc

CONF = cfg.CONF
LOG = logging.getLogger(__name__)
_ENFORCER = None


def reset_policy():
    global _ENFORCER
    if _ENFORCER:
        _ENFORCER.clear()
        _ENFORCER = None


def setup_policy():
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = policy.Enforcer(CONF)
        register_rules(_ENFORCER)


def _enforce_policy(action, target, credentials, do_raise=True):
    extras = {}
    if do_raise:
        extras.update(exc=exc.ActionForbidden, do_raise=do_raise)

    # `oslo.policy` supports both enforce and authorize. authorize is
    # stricter because it'll raise an exception if the policy action is
    # not found in the list of registered rules. This means that attempting
    # to enforce anything not found in ``armada.common.policies`` will error
    # out with a 'Policy not registered' message and 403 status code.
    try:
        _ENFORCER.authorize(
            action, target, credentials.to_policy_view(), **extras)
    except policy.PolicyNotRegistered:
        LOG.exception(
            'Policy not registered for %(action)s', {'action': action})
        raise exc.ActionForbidden()
    except Exception:
        with excutils.save_and_reraise_exception():
            LOG.debug(
                'Policy check for %(action)s failed with credentials '
                '%(credentials)s', {
                    'action': action,
                    'credentials': credentials
                })


# NOTE(felipemonteiro): This naming is OK. It's just kept around for legacy
# reasons. What's important is that authorize is used above.
def enforce(rule):
    def decorator(func):
        @functools.wraps(func)
        def handler(*args, **kwargs):
            setup_policy()
            context = args[1].context
            _enforce_policy(rule, {}, context, do_raise=True)
            return func(*args, **kwargs)

        return handler

    return decorator


def register_rules(enforcer):
    enforcer.register_defaults(policies.list_rules())
