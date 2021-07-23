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
import json

import falcon
from oslo_config import cfg
from oslo_log import log as logging

from armada import api
from armada.common import policy
CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class Status(api.BaseResource):
    @policy.enforce('tiller:get_status')
    def on_get(self, req, resp):
        '''
        get tiller status
        '''
        try:
            message = self.handle()
            resp.status = falcon.HTTP_200
            resp.text = json.dumps(message)
            resp.content_type = 'application/json'
        except Exception as e:
            err_message = 'Failed to get Tiller Status: {}'.format(e)
            self.error(req.context, err_message)
            self.return_error(resp, falcon.HTTP_500, message=err_message)

    def handle(self):
        message = {'tiller': {'state': True, 'version': "v1.2.3"}}
        return message
