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

import json

import falcon
from oslo_config import cfg

from armada import api
from armada.common import policy
from armada.handlers.tiller import Tiller

CONF = cfg.CONF


class Rollback(api.BaseResource):
    """Controller for performing a rollback of a release
    """

    @policy.enforce('armada:rollback_release')
    def on_post(self, req, resp, release):
        try:
            dry_run = req.get_param_as_bool('dry_run')

            tiller = Tiller(
                tiller_host=req.get_param('tiller_host'),
                tiller_port=req.get_param_as_int('tiller_port') or
                CONF.tiller_port,
                tiller_namespace=req.get_param(
                    'tiller_namespace', default=CONF.tiller_namespace),
                dry_run=dry_run)

            tiller.rollback_release(
                release,
                req.get_param_as_int('version') or 0,
                wait=req.get_param_as_bool('wait'),
                timeout=req.get_param_as_int('timeout') or 0,
                force=req.get_param_as_bool('force'),
                recreate_pods=req.get_param_as_bool('recreate_pods'))

            resp.body = json.dumps({
                'message': ('(dry run) ' if dry_run else '') +
                'Rollback of {} complete.'.format(release),
            })

            resp.content_type = 'application/json'
            resp.status = falcon.HTTP_200
        except Exception as e:
            self.logger.exception('Caught unexpected exception')
            err_message = 'Failed to rollback release: {}'.format(e)
            self.error(req.context, err_message)
            self.return_error(resp, falcon.HTTP_500, message=err_message)
