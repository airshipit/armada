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


class Releases(api.BaseResource):
    @policy.enforce('armada:get_release')
    def on_get(self, req, resp):
        '''Controller for listing Helm releases.
        '''
        try:
            with self.get_helm(req, resp) as helm:
                releases = self.handle(helm)
                resp.text = json.dumps({
                    'releases': releases,
                })
                resp.content_type = 'application/json'
                resp.status = falcon.HTTP_200

        except Exception as e:
            err_message = 'Unable to find Helm Releases: {}'.format(e)
            self.error(req.context, err_message)
            self.return_error(resp, falcon.HTTP_500, message=err_message)

    def handle(self, helm):
        LOG.debug('Getting helm releases')

        releases = {}
        for release in helm.list_release_ids():
            releases.setdefault(release.namespace, [])
            releases[release.namespace].append(release.name)
        return releases
