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

import falcon
from oslo_config import cfg
from oslo_policy import policy
from oslo_log import log as logging

from armada import conf
from armada.api import ArmadaRequest, HEALTH_PATH, METRICS_PATH
from armada.api.controller.armada import Apply
from armada.api.middleware import AuthMiddleware
from armada.api.middleware import ContextMiddleware
from armada.api.middleware import LoggingMiddleware
from armada.api.controller.test import TestReleasesReleaseNameController
from armada.api.controller.test import TestReleasesManifestController
from armada.api.controller.health import Health
from armada.api.controller.metrics import Metrics
from armada.api.controller.releases import Releases
from armada.api.controller.tiller import Status
from armada.api.controller.validation import Validate
from armada.api.controller.versions import Versions
from armada.exceptions import base_exception as exceptions

CONF = cfg.CONF


def create(enable_middleware=None):
    """Entry point for initializing Armada server.

    :param enable_middleware: Whether to enable middleware.
    :type enable_middleware: bool
    """
    if enable_middleware is None:
        enable_middleware = getattr(CONF, "middleware", True)

    if enable_middleware:
        api = falcon.App(
            request_type=ArmadaRequest,
            middleware=[
                AuthMiddleware(),
                ContextMiddleware(),
                LoggingMiddleware(),
            ])
    else:
        api = falcon.App(request_type=ArmadaRequest)

    logging.set_defaults(default_log_levels=CONF.default_log_levels)
    logging.setup(CONF, 'armada')

    # Configure API routing
    url_routes_v1 = [
        (HEALTH_PATH, Health()),
        ('apply', Apply()),
        ('releases', Releases()),
        # TODO: Remove this in follow on release after Shipyard has
        # been updated to no longer depend on it.
        ('status', Status()),
        ('tests', TestReleasesManifestController()),
        ('test/{namespace}/{release}', TestReleasesReleaseNameController()),
        ('validatedesign', Validate()),
        (METRICS_PATH, Metrics()),
    ]

    for route, service in url_routes_v1:
        api.add_route("/api/v1.0/{}".format(route), service)
    api.add_route('/versions', Versions())

    # Error handlers (FILO handling)
    api.add_error_handler(Exception, exceptions.default_exception_handler)
    api.add_error_handler(
        exceptions.ArmadaAPIException, exceptions.ArmadaAPIException.handle)

    # Built-in error serializer
    api.set_error_serializer(exceptions.default_error_serializer)

    return api


def paste_start_armada(global_conf, **local_conf):
    # Initialize configuration
    conf.set_app_default_configs()

    # Ensure CONF is initialized before using it
    if not CONF.config_file:
        raise RuntimeError(
            "Configuration files are not loaded. "
            " Ensure 'armada.conf' is accessible.")

    # Create and return the API
    api = create()
    return api


if __name__ == "__main__":
    conf.set_app_default_configs()

    # Ensure CONF is initialized before using it
    if not CONF.config_file:
        raise RuntimeError(
            "Configuration files are not loaded. "
            "Ensure 'armada.conf' is accessible.")

    enforcer = policy.Enforcer(CONF)
    api = create()
