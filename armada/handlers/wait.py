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
import time

from oslo_log import log as logging

from armada.utils.release import label_selectors
from armada.const import DEFAULT_K8S_TIMEOUT
from armada.exceptions import k8s_exceptions
from armada.exceptions import armada_exceptions
from kubernetes import watch

LOG = logging.getLogger(__name__)

ROLLING_UPDATE_STRATEGY_TYPE = 'RollingUpdate'


def get_wait_for(resource_type, k8s, **kwargs):

    if resource_type == 'pod':
        return PodWait(resource_type, k8s, **kwargs)
    elif resource_type == 'job':
        return JobWait(resource_type, k8s, **kwargs)

    # TODO: Also validate this up front in armada validate flow.
    raise armada_exceptions.InvalidWaitTypeException(resource_type)


class Wait(ABC):

    def __init__(self,
                 resource_type,
                 k8s,
                 get_resources,
                 skip_if_none_found=False):
        self.resource_type = resource_type
        self.k8s = k8s
        self.get_resources = get_resources
        self.skip_if_none_found = skip_if_none_found

    @abstractmethod
    def is_resource_ready(self, resource):
        '''
        :param resource: resource to check readiness of.
        :returns: 3-tuple of (status message, ready bool, error message).
        '''
        pass

    def handle_resource(self, resource):
        resource_name = resource.metadata.name

        message, resource_ready, err = self.is_resource_ready(resource)

        if err:
            # TODO: Handle error
            pass
        elif resource_ready:
            LOG.debug('Resource %s is ready!', resource_name)
        else:
            LOG.debug('Resource %s not ready: %s', resource_name, message)

        return resource_ready

    def wait(self,
             labels,
             namespace,
             timeout=DEFAULT_K8S_TIMEOUT,
             k8s_wait_attempts=1,
             k8s_wait_attempt_sleep=1):
        '''
        Wait until all resources become ready given the filters provided by
        ``labels`` and ``namespace``.

        :param namespace: namespace of resources to wait on
        :param labels: labels of resources to wait on
        :param timeout: time before disconnecting ``Watch`` stream
        :param k8s_wait_attempts: number of times to attempt waiting
            for resources to become ready (minimum 1).
        :param k8s_wait_attempt_sleep: time in seconds to sleep
            between attempts (minimum 1).
        '''

        label_selector = label_selectors(labels) if labels else ''

        wait_attempts = (k8s_wait_attempts if k8s_wait_attempts >= 1 else 1)
        sleep_time = (k8s_wait_attempt_sleep
                      if k8s_wait_attempt_sleep >= 1 else 1)

        LOG.info(
            "Waiting for resource type=%s, namespace=%s labels=%s for %ss "
            "(k8s wait %s times, sleep %ss)", self.resource_type, namespace,
            label_selector, timeout, wait_attempts, sleep_time)

        if not label_selector:
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
                LOG.info('Timed out while waiting for resources.')
                raise k8s_exceptions.KubernetesWatchTimeoutException(
                    'Timed out while waiting on namespace=(%s) labels=(%s)' %
                    (namespace, label_selector))

            timed_out, modified, unready, found_resources = (
                self._watch_resource_completions(
                    namespace=namespace,
                    label_selector=label_selector,
                    timeout=deadline_remaining))

            if not found_resources:
                if self.skip_if_none_found:
                    return
                else:
                    LOG.warn(
                        'Saw no resources for '
                        'resource type=%s, namespace=%s, labels=(%s). Are the '
                        'labels correct?', self.resource_type, namespace,
                        label_selector)

            # TODO(seaneagan): Should probably fail here even when resources
            # were not found, at least once we have an option to ignore
            # wait timeouts.
            if timed_out and found_resources:
                LOG.info('Timed out waiting for resources: %s',
                         sorted(unready))
                raise k8s_exceptions.KubernetesWatchTimeoutException(
                    'Timed out while waiting on namespace=(%s) labels=(%s)' %
                    (namespace, label_selector))

            if modified:
                successes = 0
                LOG.debug('Found modified resources: %s', sorted(modified))
            else:
                successes += 1
                LOG.debug('Found no modified resources.')

            if successes >= wait_attempts:
                break

            LOG.debug(
                'Continuing to wait: {} consecutive attempts without '
                'modified resources of {} required.', successes, wait_attempts)

            time.sleep(sleep_time)

    def _watch_resource_completions(self,
                                    namespace,
                                    label_selector,
                                    timeout=100):
        '''
        Watch and wait for resource completions.
        Returns lists of resources in various conditions for the calling
        function to handle.
        '''
        LOG.debug(
            'Starting to wait on: namespace=%s, resource type=%s, '
            'label_selector=(%s), timeout=%s', namespace, self.resource_type,
            label_selector, timeout)
        ready = {}
        modified = set()
        found_resources = False

        kwargs = {
            'namespace': namespace,
            'label_selector': label_selector,
            'timeout_seconds': timeout
        }

        resource_list = self.get_resources(**kwargs)
        for resource in resource_list.items:
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
            msg = ('Watch event: type=%s, name=%s, namespace=%s,'
                   'resource_version=%s')
            LOG.debug(msg, event_type, resource_name, namespace,
                      resource_version)

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


class PodWait(Wait):

    def __init__(self, resource_type, k8s, **kwargs):
        super(PodWait, self).__init__(resource_type, k8s,
                                      k8s.client.list_namespaced_pod, **kwargs)

    def is_resource_ready(self, resource):
        pod = resource
        name = pod.metadata.name

        status = pod.status
        phase = status.phase

        if phase == 'Succeeded':
            return ("Pod {} succeeded\n".format(name), True, None)

        if phase == 'Running':
            cond = self._get_resource_condition(status.conditions, 'Ready')
            if cond and cond.status == 'True':
                return ("Pod {} ready\n".format(name), True, None)

        msg = "Waiting for pod {} to be ready...\n"
        return (msg.format(name), False, None)


class JobWait(Wait):

    def __init__(self, resource_type, k8s, **kwargs):
        super(JobWait, self).__init__(
            resource_type, k8s, k8s.batch_api.list_namespaced_job, **kwargs)

    def is_resource_ready(self, resource):
        job = resource
        name = job.metadata.name

        expected = job.spec.completions
        completed = job.status.succeeded

        if expected != completed:
            msg = "Waiting for job {} to be successfully completed...\n"
            return (msg.format(name), False, None)
        msg = "job {} successfully completed\n"
        return (msg.format(name), True, None)
