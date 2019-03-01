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

from abc import ABC, abstractmethod
import collections
import math
import re
import time

from oslo_log import log as logging

from armada import const
from armada.utils.helm import is_test_pod
from armada.utils.release import label_selectors
from armada.exceptions import k8s_exceptions
from armada.exceptions import manifest_exceptions
from armada.exceptions import armada_exceptions
from kubernetes import watch

LOG = logging.getLogger(__name__)

ROLLING_UPDATE_STRATEGY_TYPE = 'RollingUpdate'


def get_wait_labels(chart):
    wait_config = chart.get('wait', {})
    return wait_config.get('labels', {})


# TODO: Validate this object up front in armada validate flow.
class ChartWait():

    def __init__(self, k8s, release_name, chart, namespace, k8s_wait_attempts,
                 k8s_wait_attempt_sleep, timeout):
        self.k8s = k8s
        self.release_name = release_name
        self.chart = chart
        self.wait_config = chart.get('wait', {})
        self.namespace = namespace
        self.k8s_wait_attempts = max(k8s_wait_attempts, 1)
        self.k8s_wait_attempt_sleep = max(k8s_wait_attempt_sleep, 1)

        resources = self.wait_config.get('resources')
        labels = get_wait_labels(self.chart)

        if resources is not None:
            waits = []
            for resource_config in resources:
                # Initialize labels
                resource_config.setdefault('labels', {})
                # Add base labels
                resource_config['labels'].update(labels)
                waits.append(self.get_resource_wait(resource_config))
        else:
            waits = [
                JobWait('job', self, labels, skip_if_none_found=True),
                PodWait('pod', self, labels)
            ]
        self.waits = waits

        # Calculate timeout
        wait_timeout = timeout
        if wait_timeout is None:
            wait_timeout = self.wait_config.get('timeout')

        # TODO(MarshM): Deprecated, remove `timeout` key.
        deprecated_timeout = self.chart.get('timeout')
        if deprecated_timeout is not None:
            LOG.warn('The `timeout` key is deprecated and support '
                     'for this will be removed soon. Use '
                     '`wait.timeout` instead.')
            if wait_timeout is None:
                wait_timeout = deprecated_timeout

        if wait_timeout is None:
            LOG.info('No Chart timeout specified, using default: %ss',
                     const.DEFAULT_CHART_TIMEOUT)
            wait_timeout = const.DEFAULT_CHART_TIMEOUT

        self.timeout = wait_timeout

    def get_timeout(self):
        return self.timeout

    def is_native_enabled(self):
        native_wait = self.wait_config.get('native', {})
        return native_wait.get('enabled', True)

    def wait(self, timeout):
        deadline = time.time() + timeout
        # TODO(seaneagan): Parallelize waits
        for wait in self.waits:
            wait.wait(timeout=timeout)
            timeout = int(round(deadline - time.time()))

    def get_resource_wait(self, resource_config):

        kwargs = dict(resource_config)
        resource_type = kwargs.pop('type')
        labels = kwargs.pop('labels')

        try:
            if resource_type == 'pod':
                return PodWait(resource_type, self, labels, **kwargs)
            elif resource_type == 'job':
                return JobWait(resource_type, self, labels, **kwargs)
            if resource_type == 'deployment':
                return DeploymentWait(resource_type, self, labels, **kwargs)
            elif resource_type == 'daemonset':
                return DaemonSetWait(resource_type, self, labels, **kwargs)
            elif resource_type == 'statefulset':
                return StatefulSetWait(resource_type, self, labels, **kwargs)
        except TypeError:
            raise manifest_exceptions.ManifestException(
                'invalid config for item in `wait.resources`: {}'.format(
                    resource_config))

        raise manifest_exceptions.ManifestException(
            'invalid `type` for item in `wait.resources`: {}'.format(
                resource_config['type']))


class ResourceWait(ABC):

    def __init__(self,
                 resource_type,
                 chart_wait,
                 labels,
                 get_resources,
                 skip_if_none_found=False):
        self.resource_type = resource_type
        self.chart_wait = chart_wait
        self.label_selector = label_selectors(labels)
        self.get_resources = get_resources
        self.skip_if_none_found = skip_if_none_found

    @abstractmethod
    def is_resource_ready(self, resource):
        '''
        :param resource: resource to check readiness of.
        :returns: 2-tuple of (status message, ready bool).
        :raises: WaitException
        '''
        pass

    def include_resource(self, resource):
        '''
        Test to include or exclude a resource in a wait operation. This method
        can be used to exclude resources that should not be included in wait
        operations (e.g. test pods).
        :param resource: resource to test
        :returns: boolean representing test result
        '''
        return True

    def handle_resource(self, resource):
        resource_name = resource.metadata.name

        try:
            message, resource_ready = self.is_resource_ready(resource)

            if resource_ready:
                LOG.debug('Resource %s is ready!', resource_name)
            else:
                LOG.debug('Resource %s not ready: %s', resource_name, message)

            return resource_ready
        except armada_exceptions.WaitException as e:
            LOG.warn('Resource %s unlikely to become ready: %s', resource_name,
                     e)
            return False

    def wait(self, timeout):
        '''
        :param timeout: time before disconnecting ``Watch`` stream
        '''

        LOG.info(
            "Waiting for resource type=%s, namespace=%s labels=%s for %ss "
            "(k8s wait %s times, sleep %ss)", self.resource_type,
            self.chart_wait.namespace, self.label_selector, timeout,
            self.chart_wait.k8s_wait_attempts,
            self.chart_wait.k8s_wait_attempt_sleep)
        if not self.label_selector:
            LOG.warn('"label_selector" not specified, waiting with no labels '
                     'may cause unintended consequences.')

        # Track the overall deadline for timing out during waits
        deadline = time.time() + timeout

        # NOTE(mark-burnett): Attempt to wait multiple times without
        # modification, in case new resources appear after our watch exits.

        successes = 0
        while True:
            deadline_remaining = int(round(deadline - time.time()))
            if deadline_remaining <= 0:
                error = (
                    "Timed out waiting for resource type={}, namespace={}, "
                    "labels={}".format(self.resource_type,
                                       self.chart_wait.namespace,
                                       self.label_selector))
                LOG.error(error)
                raise k8s_exceptions.KubernetesWatchTimeoutException(error)

            timed_out, modified, unready, found_resources = (
                self._watch_resource_completions(timeout=deadline_remaining))

            if (not found_resources) and self.skip_if_none_found:
                return

            if timed_out:
                if not found_resources:
                    details = ('None found! Are `wait.labels` correct? Does '
                               '`wait.resources` need to exclude %s?'.format(
                                   self.resource_type))
                else:
                    details = ('These {}s were not ready={}'.format(
                        self.resource_type, sorted(unready)))
                error = (
                    'Timed out waiting for {}s (namespace={}, labels=({})). {}'
                    .format(self.resource_type, self.chart_wait.namespace,
                            self.label_selector, details))
                LOG.error(error)
                raise k8s_exceptions.KubernetesWatchTimeoutException(error)

            if modified:
                successes = 0
                LOG.debug('Found modified resources: %s', sorted(modified))
            else:
                successes += 1
                LOG.debug('Found no modified resources.')

            if successes >= self.chart_wait.k8s_wait_attempts:
                break

            LOG.debug(
                'Continuing to wait: %s consecutive attempts without '
                'modified resources of %s required.', successes,
                self.chart_wait.k8s_wait_attempts)
            time.sleep(self.chart_wait.k8s_wait_attempt_sleep)

        return True

    def _watch_resource_completions(self, timeout):
        '''
        Watch and wait for resource completions.
        Returns lists of resources in various conditions for the calling
        function to handle.
        '''
        LOG.debug(
            'Starting to wait on: namespace=%s, resource type=%s, '
            'label_selector=(%s), timeout=%s', self.chart_wait.namespace,
            self.resource_type, self.label_selector, timeout)
        ready = {}
        modified = set()
        found_resources = False

        kwargs = {
            'namespace': self.chart_wait.namespace,
            'label_selector': self.label_selector,
            'timeout_seconds': timeout
        }

        resource_list = self.get_resources(**kwargs)
        for resource in resource_list.items:
            # Only include resources that should be included in wait ops
            if self.include_resource(resource):
                ready[resource.metadata.name] = self.handle_resource(resource)
        if not resource_list.items:
            if self.skip_if_none_found:
                msg = 'Skipping wait, no %s resources found.'
                LOG.debug(msg, self.resource_type)
                return (False, modified, [], found_resources)
        else:
            found_resources = True
            if all(ready.values()):
                return (False, modified, [], found_resources)

        # Only watch new events.
        kwargs['resource_version'] = resource_list.metadata.resource_version

        w = watch.Watch()
        for event in w.stream(self.get_resources, **kwargs):
            event_type = event['type'].upper()
            resource = event['object']
            resource_name = resource.metadata.name
            resource_version = resource.metadata.resource_version

            # Skip resources that should be excluded from wait operations
            if not self.include_resource(resource):
                continue

            msg = ('Watch event: type=%s, name=%s, namespace=%s,'
                   'resource_version=%s')
            LOG.debug(msg, event_type, resource_name,
                      self.chart_wait.namespace, resource_version)

            if event_type in {'ADDED', 'MODIFIED'}:
                found_resources = True
                resource_ready = self.handle_resource(resource)
                ready[resource_name] = resource_ready

                if event_type == 'MODIFIED':
                    modified.add(resource_name)

            elif event_type == 'DELETED':
                LOG.debug('Resource %s: removed from tracking', resource_name)
                ready.pop(resource_name)

            elif event_type == 'ERROR':
                LOG.error('Resource %s: Got error event %s', resource_name,
                          event['object'].to_dict())
                raise k8s_exceptions.KubernetesErrorEventException(
                    'Got error event for resource: %s' % event['object'])

            else:
                LOG.error('Unrecognized event type (%s) for resource: %s',
                          event_type, event['object'])
                raise (k8s_exceptions.
                       KubernetesUnknownStreamingEventTypeException(
                           'Got unknown event type (%s) for resource: %s' %
                           (event_type, event['object'])))

            if all(ready.values()):
                return (False, modified, [], found_resources)

        return (True, modified,
                [name for name, is_ready in ready.items() if not is_ready],
                found_resources)

    def _get_resource_condition(self, resource_conditions, condition_type):
        for pc in resource_conditions:
            if pc.type == condition_type:
                return pc


class PodWait(ResourceWait):

    def __init__(self, resource_type, chart_wait, labels, **kwargs):
        super(PodWait, self).__init__(
            resource_type, chart_wait, labels,
            chart_wait.k8s.client.list_namespaced_pod, **kwargs)

    def include_resource(self, resource):
        pod = resource
        include = not is_test_pod(pod)

        # NOTE(drewwalters96): Test pods may cause wait operations to fail
        # when old resources remain from previous upgrades/tests. Indicate that
        # test pods should not be included in wait operations.
        if not include:
            LOG.debug('Test pod %s will be skipped during wait operations.',
                      pod.metadata.name)

        return include

    def is_resource_ready(self, resource):
        pod = resource
        name = pod.metadata.name

        status = pod.status
        phase = status.phase

        if phase == 'Succeeded':
            return ("Pod {} succeeded".format(name), True)

        if phase == 'Running':
            cond = self._get_resource_condition(status.conditions, 'Ready')
            if cond and cond.status == 'True':
                return ("Pod {} ready".format(name), True)

        msg = "Waiting for pod {} to be ready..."
        return (msg.format(name), False)


class JobWait(ResourceWait):

    def __init__(self, resource_type, chart_wait, labels, **kwargs):
        super(JobWait, self).__init__(
            resource_type, chart_wait, labels,
            chart_wait.k8s.batch_api.list_namespaced_job, **kwargs)

    def is_resource_ready(self, resource):
        job = resource
        name = job.metadata.name

        expected = job.spec.completions
        completed = job.status.succeeded

        if expected != completed:
            msg = "Waiting for job {} to be successfully completed..."
            return (msg.format(name), False)
        msg = "job {} successfully completed"
        return (msg.format(name), True)


CountOrPercent = collections.namedtuple('CountOrPercent',
                                        'number is_percent source')

# Controller logic (Deployment, DaemonSet, StatefulSet) is adapted from
# `kubectl rollout status`:
# https://github.com/kubernetes/kubernetes/blob/master/pkg/kubectl/rollout_status.go


class ControllerWait(ResourceWait):

    def __init__(self,
                 resource_type,
                 chart_wait,
                 labels,
                 get_resources,
                 min_ready="100%",
                 **kwargs):
        super(ControllerWait, self).__init__(resource_type, chart_wait, labels,
                                             get_resources, **kwargs)

        if isinstance(min_ready, str):
            match = re.match('(.*)%$', min_ready)
            if match:
                min_ready_percent = int(match.group(1))
                self.min_ready = CountOrPercent(
                    number=min_ready_percent,
                    is_percent=True,
                    source=min_ready)
            else:
                raise manifest_exceptions.ManifestException(
                    "`min_ready` as string must be formatted as a percent "
                    "e.g. '80%'")
        else:
            self.min_ready = CountOrPercent(
                number=min_ready, is_percent=False, source=min_ready)

    def _is_min_ready(self, ready, total):
        if self.min_ready.is_percent:
            min_ready = math.ceil(total * (self.min_ready.number / 100))
        else:
            min_ready = self.min_ready.number
        return ready >= min_ready


class DeploymentWait(ControllerWait):

    def __init__(self, resource_type, chart_wait, labels, **kwargs):
        super(DeploymentWait, self).__init__(
            resource_type, chart_wait, labels,
            chart_wait.k8s.apps_v1_api.list_namespaced_deployment, **kwargs)

    def is_resource_ready(self, resource):
        deployment = resource
        name = deployment.metadata.name
        spec = deployment.spec
        status = deployment.status

        gen = deployment.metadata.generation or 0
        observed_gen = status.observed_generation or 0
        if gen <= observed_gen:
            cond = self._get_resource_condition(status.conditions,
                                                'Progressing')
            if cond and (cond.reason or '') == 'ProgressDeadlineExceeded':
                msg = "deployment {} exceeded its progress deadline"
                return ("", False, msg.format(name))

            replicas = spec.replicas or 0
            updated_replicas = status.updated_replicas or 0
            available_replicas = status.available_replicas or 0
            if updated_replicas < replicas:
                msg = ("Waiting for deployment {} rollout to finish: {} out "
                       "of {} new replicas have been updated...")
                return (msg.format(name, updated_replicas, replicas), False)

            if replicas > updated_replicas:
                msg = ("Waiting for deployment {} rollout to finish: {} old "
                       "replicas are pending termination...")
                pending = replicas - updated_replicas
                return (msg.format(name, pending), False)

            if not self._is_min_ready(available_replicas, updated_replicas):
                msg = ("Waiting for deployment {} rollout to finish: {} of {} "
                       "updated replicas are available, with min_ready={}")
                return (msg.format(name, available_replicas, updated_replicas,
                                   self.min_ready.source), False, None)
            msg = "deployment {} successfully rolled out\n"
            return (msg.format(name), True)

        msg = "Waiting for deployment spec update to be observed..."
        return (msg.format(), False)


class DaemonSetWait(ControllerWait):

    def __init__(self, resource_type, chart_wait, labels, **kwargs):
        super(DaemonSetWait, self).__init__(
            resource_type, chart_wait, labels,
            chart_wait.k8s.apps_v1_api.list_namespaced_daemon_set, **kwargs)

    def is_resource_ready(self, resource):
        daemon = resource
        name = daemon.metadata.name
        spec = daemon.spec
        status = daemon.status

        if spec.update_strategy.type != ROLLING_UPDATE_STRATEGY_TYPE:
            msg = ("Assuming non-readiness for strategy type {}, can only "
                   "determine for {}")
            raise armada_exceptions.WaitException(
                msg.format(spec.update_strategy.type,
                           ROLLING_UPDATE_STRATEGY_TYPE))

        gen = daemon.metadata.generation or 0
        observed_gen = status.observed_generation or 0
        updated_number_scheduled = status.updated_number_scheduled or 0
        desired_number_scheduled = status.desired_number_scheduled or 0
        number_available = status.number_available or 0
        if gen <= observed_gen:
            if (updated_number_scheduled < desired_number_scheduled):
                msg = ("Waiting for daemon set {} rollout to finish: {} out "
                       "of {} new pods have been updated...")
                return (msg.format(name, updated_number_scheduled,
                                   desired_number_scheduled), False)

            if not self._is_min_ready(number_available,
                                      desired_number_scheduled):
                msg = ("Waiting for daemon set {} rollout to finish: {} of {} "
                       "updated pods are available, with min_ready={}")
                return (msg.format(name, number_available,
                                   desired_number_scheduled,
                                   self.min_ready.source), False)

            msg = "daemon set {} successfully rolled out"
            return (msg.format(name), True)

        msg = "Waiting for daemon set spec update to be observed..."
        return (msg.format(), False)


class StatefulSetWait(ControllerWait):

    def __init__(self, resource_type, chart_wait, labels, **kwargs):
        super(StatefulSetWait, self).__init__(
            resource_type, chart_wait, labels,
            chart_wait.k8s.apps_v1_api.list_namespaced_stateful_set, **kwargs)

    def is_resource_ready(self, resource):
        sts = resource
        name = sts.metadata.name
        spec = sts.spec
        status = sts.status

        update_strategy_type = spec.update_strategy.type or ''
        if update_strategy_type != ROLLING_UPDATE_STRATEGY_TYPE:
            msg = ("Assuming non-readiness for strategy type {}, can only "
                   "determine for {}")

            raise armada_exceptions.WaitException(
                msg.format(update_strategy_type, ROLLING_UPDATE_STRATEGY_TYPE))

        gen = sts.metadata.generation or 0
        observed_gen = status.observed_generation or 0
        if (observed_gen == 0 or gen > observed_gen):
            msg = "Waiting for statefulset spec update to be observed..."
            return (msg, False)

        replicas = spec.replicas or 0
        ready_replicas = status.ready_replicas or 0
        updated_replicas = status.updated_replicas or 0
        current_replicas = status.current_replicas or 0

        if replicas and not self._is_min_ready(ready_replicas, replicas):
            msg = ("Waiting for statefulset {} rollout to finish: {} of {} "
                   "pods are ready, with min_ready={}")
            return (msg.format(name, ready_replicas, replicas,
                               self.min_ready.source), False)

        if (update_strategy_type == ROLLING_UPDATE_STRATEGY_TYPE and
                spec.update_strategy.rolling_update):
            if replicas and spec.update_strategy.rolling_update.partition:
                msg = ("Waiting on partitioned rollout not supported, "
                       "assuming non-readiness of statefulset {}")
                return (msg.format(name), False)

        update_revision = status.update_revision or 0
        current_revision = status.current_revision or 0

        if update_revision != current_revision:
            msg = ("waiting for statefulset rolling update to complete {} "
                   "pods at revision {}...")
            return (msg.format(updated_replicas, update_revision), False)

        msg = "statefulset rolling update complete {} pods at revision {}..."
        return (msg.format(current_replicas, current_revision), True)
