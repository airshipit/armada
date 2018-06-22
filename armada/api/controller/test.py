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
import yaml

import falcon
from oslo_config import cfg

from armada import api
from armada.common import policy
from armada import const
from armada.handlers.test import test_release_for_success
from armada.handlers.tiller import Tiller
from armada.handlers.manifest import Manifest
from armada.utils.release import release_prefixer
from armada.utils import validate

CONF = cfg.CONF


class TestReleasesReleaseNameController(api.BaseResource):
    '''
    Test Helm releases via release name.
    '''

    @policy.enforce('armada:test_release')
    def on_get(self, req, resp, release):
        self.logger.info('RUNNING: %s', release)
        try:
            tiller = Tiller(
                tiller_host=req.get_param('tiller_host'),
                tiller_port=req.get_param_as_int('tiller_port') or
                CONF.tiller_port,
                tiller_namespace=req.get_param(
                    'tiller_namespace', default=CONF.tiller_namespace))
            cleanup = req.get_param_as_bool('cleanup')
            if cleanup is None:
                cleanup = False
            success = test_release_for_success(
                tiller, release, cleanup=cleanup)
        # TODO(fmontei): Provide more sensible exception(s) here.
        except Exception as e:
            err_message = 'Failed to test {}: {}'.format(release, e)
            self.error(req.context, err_message)
            return self.return_error(
                resp, falcon.HTTP_500, message=err_message)

        if success:
            msg = {
                'result': 'PASSED: {}'.format(release),
                'message': 'MESSAGE: Test Pass'
            }
        else:
            msg = {
                'result': 'FAILED: {}'.format(release),
                'message': 'MESSAGE: Test Fail'
            }

        self.logger.info(msg)

        resp.body = json.dumps(msg)
        resp.status = falcon.HTTP_200
        resp.content_type = 'application/json'


class TestReleasesManifestController(api.BaseResource):
    '''
    Test Helm releases via a Manifest.
    '''

    def _format_validation_response(self, req, resp, result, details):
        resp.content_type = 'application/json'
        resp_body = {
            'kind': 'Status',
            'apiVersion': 'v1.0',
            'metadata': {},
            'reason': 'Validation',
            'details': {},
        }

        error_details = [m for m in details if m.get('error', False)]

        resp_body['details']['errorCount'] = len(error_details)
        resp_body['details']['messageList'] = details

        if result:
            resp.status = falcon.HTTP_200
            resp_body['status'] = 'Success'
            resp_body['message'] = 'Armada validations succeeded.'
            resp_body['code'] = 200
        else:
            resp.status = falcon.HTTP_400
            resp_body['status'] = 'Failure'
            resp_body['message'] = (
                'Failed to validate documents or generate Armada Manifest '
                'from documents.')
            resp_body['code'] = 400
            self.error(req.context, resp_body['message'])

        resp.body = json.dumps(resp_body)
        return result

    def _validate_documents(self, req, resp, documents):
        result, details = validate.validate_armada_documents(documents)
        return self._format_validation_response(req, resp, result, details)

    @policy.enforce('armada:tests_manifest')
    def on_post(self, req, resp):
        # TODO(fmontei): Validation Content-Type is application/x-yaml.

        target_manifest = req.get_param('target_manifest', None)

        try:
            tiller = Tiller(
                tiller_host=req.get_param('tiller_host'),
                tiller_port=req.get_param_as_int('tiller_port') or
                CONF.tiller_port,
                tiller_namespace=req.get_param(
                    'tiller_namespace', default=CONF.tiller_namespace))
        # TODO(fmontei): Provide more sensible exception(s) here.
        except Exception:
            err_message = 'Failed to initialize Tiller handler.'
            self.error(req.context, err_message)
            return self.return_error(
                resp, falcon.HTTP_500, message=err_message)

        try:
            documents = self.req_yaml(req, default=[])
        except yaml.YAMLError:
            err_message = 'Documents must be valid YAML.'
            return self.return_error(
                resp, falcon.HTTP_400, message=err_message)

        is_valid = self._validate_documents(req, resp, documents)
        if not is_valid:
            return resp

        armada_obj = Manifest(
            documents, target_manifest=target_manifest).get_manifest()

        prefix = armada_obj.get(const.KEYWORD_ARMADA).get(const.KEYWORD_PREFIX)
        known_releases = [release[0] for release in tiller.list_charts()]

        message = {'tests': {'passed': [], 'skipped': [], 'failed': []}}

        for group in armada_obj.get(const.KEYWORD_ARMADA).get(
                const.KEYWORD_GROUPS):
            for ch in group.get(const.KEYWORD_CHARTS):
                chart = ch['chart']
                release_name = release_prefixer(prefix, chart.get('release'))
                cleanup = req.get_param_as_bool('cleanup')
                if cleanup is None:
                    test_chart_override = chart.get('test', {})
                    if isinstance(test_chart_override, bool):
                        self.logger.warn(
                            'Boolean value for chart `test` key is deprecated '
                            'and will be removed. Use `test.enabled` instead.')
                        # Use old default value.
                        cleanup = True
                    else:
                        cleanup = test_chart_override.get('options', {}).get(
                            'cleanup', False)
                if release_name in known_releases:
                    self.logger.info('RUNNING: %s tests', release_name)
                    success = test_release_for_success(
                        tiller, release_name, cleanup=cleanup)
                    if success:
                        self.logger.info("PASSED: %s", release_name)
                        message['test']['passed'].append(release_name)
                    else:
                        self.logger.info("FAILED: %s", release_name)
                        message['test']['failed'].append(release_name)
                else:
                    self.logger.info('Release %s not found - SKIPPING',
                                     release_name)
                    message['test']['skipped'].append(release_name)

        resp.status = falcon.HTTP_200
        resp.body = json.dumps(message)
        resp.content_type = 'application/json'
