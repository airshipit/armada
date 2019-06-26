# Copyright 2019 The Armada Authors.
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

import falcon
import prometheus_client

from armada import api
from armada.handlers import metrics


class Metrics(api.BaseResource):
    '''Controller for exporting prometheus metrics.
    '''

    def on_get(self, req, resp):
        encoder, content_type = prometheus_client.exposition.choose_encoder(
            req.get_header('Accept'))
        try:
            output = encoder(metrics.REGISTRY)
        except Exception as ex:
            err_message = 'Failed to generate metric output'
            self.logger.error(err_message, exc_info=ex)
            return self.return_error(
                resp, falcon.HTTP_500, message=err_message)
        resp.content_type = content_type
        resp.body = output
        resp.status = falcon.HTTP_200
