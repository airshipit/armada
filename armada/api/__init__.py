# Copyright 2017 The Armada Authors.  All other rights reserved.
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
# limitations under the License

import json
import logging as log
import uuid

import falcon
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
import yaml

from armada.handlers.helm import Helm

CONF = cfg.CONF

HEALTH_PATH = 'health'
METRICS_PATH = 'metrics'


class BaseResource(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def on_options(self, req, resp):
        self_attrs = dir(self)
        methods = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH']
        allowed_methods = []

        for m in methods:
            if 'on_' + m.lower() in self_attrs:
                allowed_methods.append(m)

        resp.headers['Allow'] = ','.join(allowed_methods)
        resp.status = falcon.HTTP_200

    def req_yaml(self, req, default=None):
        if req.content_length is None or req.content_length == 0:
            return default

        raw_body = req.stream.read(req.content_length or 0)

        if raw_body is None:
            return default

        try:
            return list(yaml.safe_load_all(raw_body.decode('utf-8')))
        except yaml.YAMLError:
            with excutils.save_and_reraise_exception():
                self.error(
                    req.context,
                    "Invalid YAML in request: \n%s" % raw_body.decode('utf-8'))

    def req_json(self, req):
        if req.content_length is None or req.content_length == 0:
            return None

        raw_body = req.stream.read(req.content_length or 0)

        if raw_body is None:
            return None

        try:
            return json.loads(raw_body.decode())
        except json.JSONDecodeError as jex:
            self.error(req.context, "Invalid JSON in request: %s" % str(jex))
            raise Exception("%s: Invalid JSON in body: %s" % (req.path, jex))

    def return_error(self, resp, status_code, message="", retry=False):
        resp.text = json.dumps(
            {
                'type': 'error',
                'message': message,
                'retry': retry
            })
        resp.status = status_code

    def log_error(self, ctx, level, msg):
        extra = {
            'user': 'N/A',
            'req_id': 'N/A',
            'external_ctx': 'N/A',
            'end_user': 'N/A',
        }

        if ctx is not None:
            extra = {
                'user': ctx.user,
                'req_id': ctx.request_id,
                'external_ctx': ctx.external_marker,
                'end_user': ctx.end_user,
            }

        self.logger.log(level, msg, extra=extra)

    def debug(self, ctx, msg):
        self.log_error(ctx, log.DEBUG, msg)

    def info(self, ctx, msg):
        self.log_error(ctx, log.INFO, msg)

    def warn(self, ctx, msg):
        self.log_error(ctx, log.WARN, msg)

    def error(self, ctx, msg):
        self.log_error(ctx, log.ERROR, msg)

    def get_helm(self, req, resp):
        return Helm()


class ArmadaRequestContext(object):
    def __init__(self):
        self.log_level = 'ERROR'
        self.user = None  # Username
        self.user_id = None  # User ID (UUID)
        self.user_domain_id = None  # Domain owning user
        self.roles = ['anyone']
        self.project_id = None
        self.project_domain_id = None  # Domain owning project
        self.is_admin_project = False
        self.authenticated = False
        self.request_id = str(uuid.uuid4())
        self.external_marker = ''
        self.end_user = None  # Initial User

    def set_log_level(self, level):
        if level in ['error', 'info', 'debug']:
            self.log_level = level

    def set_user(self, user):
        self.user = user

    def set_project(self, project):
        self.project = project

    def add_role(self, role):
        self.roles.append(role)

    def add_roles(self, roles):
        self.roles.extend(roles)

    def remove_role(self, role):
        self.roles = [x for x in self.roles if x != role]

    def set_external_marker(self, marker):
        self.external_marker = marker

    def set_end_user(self, end_user):
        self.end_user = end_user

    def to_policy_view(self):
        policy_dict = {}

        policy_dict['user_id'] = self.user_id
        policy_dict['user_domain_id'] = self.user_domain_id
        policy_dict['project_id'] = self.project_id
        policy_dict['project_domain_id'] = self.project_domain_id
        policy_dict['roles'] = self.roles
        policy_dict['is_admin_project'] = self.is_admin_project

        return policy_dict


class ArmadaRequest(falcon.request.Request):
    context_type = ArmadaRequestContext
