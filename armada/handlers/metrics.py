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

from contextlib import ExitStack
from enum import Enum
import os

import prometheus_client
from prometheus_client import multiprocess, values, context_managers


class ActionMetrics():
    """ Support for defining and observing metrics for an action, including
    tracking attempts, failures, and timing.
    """

    _PREFIX = 'armada'

    def __init__(self, prefix, description, labels):
        """
        :param prefix: prefix to use for each metric name
        :param description: description of action to use in metric description
        :param labels: label names to define for each metric
        """
        self.full_prefix = '{}_{}'.format(self.__class__._PREFIX, prefix)
        self.progress = prometheus_client.Gauge(
            '{}_attempt_inprogress'.format(self.full_prefix),
            'In progress attempts to {}'.format(description),
            labels,
            registry=REGISTRY,
            multiprocess_mode='livesum')
        self.attempt_total = prometheus_client.Counter(
            '{}_attempt_total'.format(self.full_prefix),
            'Total attempts to {}'.format(description),
            labels,
            registry=REGISTRY)
        self.failure_total = prometheus_client.Counter(
            '{}_failure_total'.format(self.full_prefix),
            'Total failures to {}'.format(description),
            labels,
            registry=REGISTRY)
        self.duration = prometheus_client.Histogram(
            '{}_duration_seconds'.format(self.full_prefix),
            'Seconds to {}'.format(description),
            labels,
            registry=REGISTRY)

    def get_context(self, *args, **kwargs):
        """ Any extra args are used as metric label values.

        :return: a context manager for the action which observes the desired
        metrics.
        :rtype: contextmanager
        """
        progress = self.progress.labels(*args, **kwargs)
        attempt_total = self.attempt_total.labels(*args, **kwargs)
        attempt_total.inc()
        failure_total = self.failure_total.labels(*args, **kwargs)
        duration = self.duration.labels(*args, **kwargs)

        e = ExitStack()
        contexts = [
            progress.track_inprogress(),
            failure_total.count_exceptions(),
            duration.time()
        ]
        for ctx in contexts:
            e.enter_context(ctx)
        return e


class ChartHandleMetrics(ActionMetrics):
    def __init__(self, prefix, description, labels):
        super().__init__(prefix, description, labels)
        self.concurrency = prometheus_client.Histogram(
            '{}_concurrency_count'.format(self.full_prefix),
            'Count of charts being handled concurrently for chart',
            labels,
            registry=REGISTRY)

    def get_context(self, concurrency_value, *args, **kwargs):
        concurrency = self.concurrency.labels(*args, **kwargs)
        concurrency.observe(concurrency_value)
        return super().get_context(*args, **kwargs)


class ActionWithTimeoutMetrics(ActionMetrics):
    def __init__(self, prefix, description, labels):
        super().__init__(prefix, description, labels)
        self.timeout = prometheus_client.Histogram(
            '{}_timeout_duration_seconds'.format(self.full_prefix),
            'Configured timeout (in seconds) to {}'.format(description),
            labels,
            registry=REGISTRY)
        self.timeout_usage = prometheus_client.Histogram(
            '{}_timeout_usage_ratio'.format(self.full_prefix),
            'Ratio of duration to timeout to {}'.format(description),
            labels,
            registry=REGISTRY)

    def get_context(self, timeout_value, *args, **kwargs):
        timeout = self.timeout.labels(*args, **kwargs)
        timeout_usage = self.timeout_usage.labels(*args, **kwargs)

        timeout.observe(timeout_value)

        def observe_timeout_usage(duration):
            # Avoid division by 0
            if timeout_value:
                val = duration / timeout_value
                timeout_usage.observe(val)

        timer = context_managers.Timer(observe_timeout_usage)
        context = super().get_context(*args, **kwargs)
        context.enter_context(timer)
        return context


class ChartDeployAction(Enum):
    """ Enum to define sub-actions for the chart deploy action, to be used as
    label values.
    """

    INSTALL = 1
    UPGRADE = 2
    NOOP = 3

    def get_label_value(self):
        """
        :return: the label value
        :rtype: str
        """
        return self.name.lower()


REGISTRY = prometheus_client.CollectorRegistry()

if "prometheus_multiproc_dir" in os.environ:
    # For why this is needed see:
    #   https://github.com/prometheus/client_python/issues/275#issuecomment-504755024
    import uwsgi
    prometheus_client.values.ValueClass = values.MultiProcessValue(
        uwsgi.worker_id)

    multiprocess.MultiProcessCollector(REGISTRY)

APPLY = ActionMetrics('apply', 'apply a manifest', ['manifest'])
# TODO: Ideally include an action (ChartDeployAction) label, but that's not
# determined until after chart handling starts.
CHART_HANDLE = ChartHandleMetrics(
    'chart_handle',
    'handle a chart (including delete, deploy, test (all as necessary) but '
    'not download)', ['manifest', 'chart'])
CHART_DOWNLOAD = ActionMetrics(
    'chart_download', 'download a chart (will be noop if previously cached)',
    ['manifest', 'chart'])
CHART_DELETE = ActionMetrics(
    'chart_delete', 'delete a chart', ['manifest', 'chart'])
CHART_DEPLOY = ActionWithTimeoutMetrics(
    'chart_deploy',
    'deploy a chart (including install/upgrade and wait (all as necessary))',
    ['manifest', 'chart', 'action'])
CHART_TEST = ActionWithTimeoutMetrics(
    'chart_test', 'test a chart', ['manifest', 'chart'])
