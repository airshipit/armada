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

import re
import time

from kubernetes import client
from kubernetes import config
from kubernetes import watch
from kubernetes.client.rest import ApiException
from oslo_config import cfg
from oslo_log import log as logging

from armada.const import DEFAULT_K8S_TIMEOUT
from armada.utils.release import label_selectors
from armada.exceptions import k8s_exceptions as exceptions

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class K8s(object):
    '''
    Object to obtain the local kube config file
    '''

    def __init__(self):
        '''
        Initialize connection to Kubernetes
        '''
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            config.load_kube_config()

        self.client = client.CoreV1Api()
        self.batch_api = client.BatchV1Api()
        self.batch_v1beta1_api = client.BatchV1beta1Api()
        self.extension_api = client.ExtensionsV1beta1Api()

    def delete_job_action(self,
                          name,
                          namespace="default",
                          propagation_policy='Foreground',
                          timeout=DEFAULT_K8S_TIMEOUT):
        '''
        Delete a job from a namespace (see _delete_item_action).

        :param name: name of job
        :param namespace: namespace
        :param propagation_policy: The Kubernetes propagation_policy to apply
            to the delete.
        :param timeout: The timeout to wait for the delete to complete
        '''
        self._delete_item_action(self.batch_api.list_namespaced_job,
                                 self.batch_api.delete_namespaced_job, "job",
                                 name, namespace, propagation_policy, timeout)

    def delete_cron_job_action(self,
                               name,
                               namespace="default",
                               propagation_policy='Foreground',
                               timeout=DEFAULT_K8S_TIMEOUT):
        '''
        Delete a cron job from a namespace (see _delete_item_action).

        :param name: name of cron job
        :param namespace: namespace
        :param propagation_policy: The Kubernetes propagation_policy to apply
            to the delete.
        :param timeout: The timeout to wait for the delete to complete
        '''
        self._delete_item_action(
            self.batch_v1beta1_api.list_namespaced_cron_job,
            self.batch_v1beta1_api.delete_namespaced_cron_job, "cron job",
            name, namespace, propagation_policy, timeout)

    def delete_pod_action(self,
                          name,
                          namespace="default",
                          propagation_policy='Foreground',
                          timeout=DEFAULT_K8S_TIMEOUT):
        '''
        Delete a pod from a namespace (see _delete_item_action).

        :param name: name of pod
        :param namespace: namespace
        :param propagation_policy: The Kubernetes propagation_policy to apply
            to the delete.
        :param timeout: The timeout to wait for the delete to complete
        '''
        self._delete_item_action(self.client.list_namespaced_pod,
                                 self.client.delete_namespaced_pod, "pod",
                                 name, namespace, propagation_policy, timeout)

    def _delete_item_action(self,
                            list_func,
                            delete_func,
                            object_type_description,
                            name,
                            namespace="default",
                            propagation_policy='Foreground',
                            timeout=DEFAULT_K8S_TIMEOUT):
        '''
        This function takes the action to delete an object (job, cronjob, pod)
        from kubernetes. It will wait for the object to be fully deleted before
        returning to processing or timing out.

        :param list_func: The callback function to list the specified object
            type
        :param delete_func: The callback function to delete the specified
            object type
        :param object_type_description: The types of objects to delete,
            in `job`, `cronjob`, or `pod`
        :param name: The name of the object to delete
        :param namespace: The namespace of the object
        :param propagation_policy: The Kubernetes propagation_policy to apply
            to the delete. Default 'Foreground' means that child objects
            will be deleted before the given object is marked as deleted.
            See: https://kubernetes.io/docs/concepts/workloads/controllers/garbage-collection/#controlling-how-the-garbage-collector-deletes-dependents  # noqa
        :param timeout: The timeout to wait for the delete to complete
        '''
        try:
            timeout = self._check_timeout(timeout)

            LOG.debug('Watching to delete %s %s, Wait timeout=%s',
                      object_type_description, name, timeout)
            body = client.V1DeleteOptions()
            w = watch.Watch()
            issue_delete = True
            found_events = False
            for event in w.stream(
                    list_func, namespace=namespace, timeout_seconds=timeout):
                if issue_delete:
                    delete_func(
                        name=name,
                        namespace=namespace,
                        body=body,
                        propagation_policy=propagation_policy)
                    issue_delete = False

                event_type = event['type'].upper()
                item_name = event['object'].metadata.name
                LOG.debug('Watch event %s on %s', event_type, item_name)

                if item_name == name:
                    found_events = True
                    if event_type == 'DELETED':
                        LOG.info('Successfully deleted %s %s',
                                 object_type_description, item_name)
                        return

            if not found_events:
                LOG.warn('Saw no delete events for %s %s in namespace=%s',
                         object_type_description, name, namespace)

            err_msg = ('Reached timeout while waiting to delete %s: '
                       'name=%s, namespace=%s' % (object_type_description,
                                                  name, namespace))
            LOG.error(err_msg)
            raise exceptions.KubernetesWatchTimeoutException(err_msg)

        except ApiException as e:
            LOG.exception("Exception when deleting %s: name=%s, namespace=%s",
                          object_type_description, name, namespace)
            raise e

    def get_namespace_job(self, namespace="default", label_selector=''):
        '''
        :param label_selector: labels of the jobs
        :param namespace: namespace of the jobs
        '''

        try:
            return self.batch_api.list_namespaced_job(
                namespace, label_selector=label_selector)
        except ApiException as e:
            LOG.error("Exception getting jobs: namespace=%s, label=%s: %s",
                      namespace, label_selector, e)

    def get_namespace_cron_job(self, namespace="default", label_selector=''):
        '''
        :param label_selector: labels of the cron jobs
        :param namespace: namespace of the cron jobs
        '''

        try:
            return self.batch_v1beta1_api.list_namespaced_cron_job(
                namespace, label_selector=label_selector)
        except ApiException as e:
            LOG.error(
                "Exception getting cron jobs: namespace=%s, label=%s: %s",
                namespace, label_selector, e)

    def get_namespace_pod(self, namespace="default", label_selector=''):
        '''
        :param namespace: namespace of the Pod
        :param label_selector: filters Pods by label

        This will return a list of objects req namespace
        '''

        return self.client.list_namespaced_pod(
            namespace, label_selector=label_selector)

    def get_namespace_daemonset(self, namespace='default', label=''):
        '''
        :param namespace: namespace of target deamonset
        :param labels: specify targeted daemonset
        '''
        return self.extension_api.list_namespaced_daemon_set(
            namespace, label_selector=label)

    def create_daemon_action(self, namespace, template):
        '''
        :param: namespace - pod namespace
        :param: template - deploy daemonset via yaml
        '''
        # we might need to load something here

        self.extension_api.create_namespaced_daemon_set(
            namespace, body=template)

    def delete_daemon_action(self, name, namespace="default", body=None):
        '''
        :param: namespace - pod namespace

        This will delete daemonset
        '''

        if body is None:
            body = client.V1DeleteOptions()

        return self.extension_api.delete_namespaced_daemon_set(
            name, namespace, body)

    def wait_for_pod_redeployment(self, old_pod_name, namespace):
        '''
        :param old_pod_name: name of pods
        :param namespace: kubernetes namespace
        '''

        base_pod_pattern = re.compile('^(.+)-[a-zA-Z0-9]+$')

        if not base_pod_pattern.match(old_pod_name):
            LOG.error('Could not identify new pod after purging %s',
                      old_pod_name)
            return

        pod_base_name = base_pod_pattern.match(old_pod_name).group(1)

        new_pod_name = ''

        w = watch.Watch()
        for event in w.stream(self.client.list_namespaced_pod, namespace):
            event_name = event['object'].metadata.name
            event_match = base_pod_pattern.match(event_name)
            if not event_match or not event_match.group(1) == pod_base_name:
                continue

            pod_conditions = event['object'].status.conditions
            # wait for new pod deployment
            if event['type'] == 'ADDED' and not pod_conditions:
                new_pod_name = event_name
            elif new_pod_name:
                for condition in pod_conditions:
                    if (condition.type == 'Ready' and
                            condition.status == 'True'):
                        LOG.info('New pod %s deployed', new_pod_name)
                        w.stop()

    def wait_get_completed_podphase(self, release,
                                    timeout=DEFAULT_K8S_TIMEOUT):
        '''
        :param release: part of namespace
        :param timeout: time before disconnecting stream
        '''
        timeout = self._check_timeout(timeout)

        w = watch.Watch()
        found_events = False
        for event in w.stream(
                self.client.list_pod_for_all_namespaces,
                timeout_seconds=timeout):
            pod_name = event['object'].metadata.name

            if release in pod_name:
                found_events = True
                pod_state = event['object'].status.phase
                if pod_state == 'Succeeded':
                    w.stop()
                    break

        if not found_events:
            LOG.warn('Saw no test events for release %s', release)

    def wait_until_ready(self,
                         release=None,
                         namespace='',
                         labels='',
                         timeout=DEFAULT_K8S_TIMEOUT,
                         k8s_wait_attempts=1,
                         k8s_wait_attempt_sleep=1):
        '''
        Wait until all pods become ready given the filters provided by
        ``release``, ``labels`` and ``namespace``.

        :param release: chart release
        :param namespace: the namespace used to filter which pods to wait on
        :param labels: the labels used to filter which pods to wait on
        :param timeout: time before disconnecting ``Watch`` stream
        :param k8s_wait_attempts: The number of times to attempt waiting
            for pods to become ready (minimum 1).
        :param k8s_wait_attempt_sleep: The time in seconds to sleep
            between attempts (minimum 1).
        '''
        timeout = self._check_timeout(timeout)

        # NOTE(MarshM) 'release' is currently unused
        label_selector = label_selectors(labels) if labels else ''

        wait_attempts = (k8s_wait_attempts if k8s_wait_attempts >= 1 else 1)
        sleep_time = (k8s_wait_attempt_sleep
                      if k8s_wait_attempt_sleep >= 1 else 1)

        LOG.debug(
            "Wait on namespace=(%s) labels=(%s) for %s sec "
            "(k8s wait %s times, sleep %ss)", namespace, label_selector,
            timeout, wait_attempts, sleep_time)

        if not namespace:
            # This shouldn't be reachable
            LOG.warn('"namespace" not specified, waiting across all available '
                     'namespaces is likely to cause unintended consequences.')
        if not label_selector:
            LOG.warn('"label_selector" not specified, waiting with no labels '
                     'may cause unintended consequences.')

        # Track the overall deadline for timing out during waits
        deadline = time.time() + timeout

        # First, we should watch for jobs before checking pods, as a job can
        # still be running even after its current pods look healthy or have
        # been removed and are pending reschedule
        found_jobs = self.get_namespace_job(namespace, label_selector)
        if len(found_jobs.items):
            self._watch_job_completion(namespace, label_selector, timeout)

        # NOTE(mark-burnett): Attempt to wait multiple times without
        # modification, in case new pods appear after our watch exits.

        successes = 0
        while successes < wait_attempts:
            deadline_remaining = int(round(deadline - time.time()))
            if deadline_remaining <= 0:
                LOG.info('Timed out while waiting for pods.')
                raise exceptions.KubernetesWatchTimeoutException(
                    'Timed out while waiting on namespace=(%s) labels=(%s)' %
                    (namespace, label_selector))

            timed_out, modified_pods, unready_pods, found_events = (
                self._watch_pod_completions(
                    namespace=namespace,
                    label_selector=label_selector,
                    timeout=deadline_remaining))

            if not found_events:
                LOG.warn(
                    'Saw no install/update events for release=%s, '
                    'namespace=%s, labels=(%s). Are the labels correct?',
                    release, namespace, label_selector)

            if timed_out:
                LOG.info('Timed out waiting for pods: %s',
                         sorted(unready_pods))
                raise exceptions.KubernetesWatchTimeoutException(
                    'Timed out while waiting on namespace=(%s) labels=(%s)' %
                    (namespace, label_selector))

            if modified_pods:
                successes = 0
                LOG.debug('Continuing to wait, found modified pods: %s',
                          sorted(modified_pods))
            else:
                successes += 1
                LOG.debug('Found no modified pods this attempt. successes=%d',
                          successes)

            time.sleep(sleep_time)

        return True

    def _watch_pod_completions(self, namespace, label_selector, timeout=100):
        '''
        Watch and wait for pod completions.
        Returns lists of pods in various conditions for the calling function
        to handle.
        '''
        LOG.debug(
            'Starting to wait on pods: namespace=%s, label_selector=(%s), '
            'timeout=%s', namespace, label_selector, timeout)
        ready_pods = {}
        modified_pods = set()
        w = watch.Watch()
        first_event = True
        found_events = False

        # Watch across specific namespace, or all
        kwargs = {
            'label_selector': label_selector,
            'timeout_seconds': timeout,
        }
        if namespace:
            func_to_call = self.client.list_namespaced_pod
            kwargs['namespace'] = namespace
        else:
            func_to_call = self.client.list_pod_for_all_namespaces

        for event in w.stream(func_to_call, **kwargs):
            if first_event:
                pod_list = func_to_call(**kwargs)
                for pod in pod_list.items:
                    LOG.debug('Setting up to wait for pod %s namespace=%s',
                              pod.metadata.name, pod.metadata.namespace)
                    ready_pods[pod.metadata.name] = False
                first_event = False

            event_type = event['type'].upper()
            pod_name = event['object'].metadata.name
            LOG.debug('Watch event for pod %s namespace=%s label_selector=%s',
                      pod_name, namespace, label_selector)

            if event_type in {'ADDED', 'MODIFIED'}:
                found_events = True
                status = event['object'].status
                pod_phase = status.phase

                pod_ready = True
                if (pod_phase == 'Succeeded' or
                    (pod_phase == 'Running' and self._get_pod_condition(
                        status.conditions, 'Ready') == 'True')):
                    LOG.debug('Pod %s is ready!', pod_name)
                else:
                    pod_ready = False
                    LOG.debug(
                        'Pod %s not ready: conditions:\n%s\n'
                        'container_statuses:\n%s', pod_name, status.conditions,
                        status.container_statuses)

                ready_pods[pod_name] = pod_ready

                if event_type == 'MODIFIED':
                    modified_pods.add(pod_name)

            elif event_type == 'DELETED':
                LOG.debug('Pod %s: removed from tracking', pod_name)
                ready_pods.pop(pod_name)

            elif event_type == 'ERROR':
                LOG.error('Pod %s: Got error event %s', pod_name,
                          event['object'].to_dict())
                raise exceptions.KubernetesErrorEventException(
                    'Got error event for pod: %s' % event['object'])

            else:
                LOG.error('Unrecognized event type (%s) for pod: %s',
                          event_type, event['object'])
                raise exceptions.KubernetesUnknownStreamingEventTypeException(
                    'Got unknown event type (%s) for pod: %s' %
                    (event_type, event['object']))

            if all(ready_pods.values()):
                return (False, modified_pods, [], found_events)

        # NOTE(mark-burnett): This path is reachable if there are no pods
        # (unlikely) or in the case of the watch timing out.
        return (not all(ready_pods.values()), modified_pods,
                [name for name, ready in ready_pods.items() if not ready],
                found_events)

    def _get_pod_condition(self, pod_conditions, condition_type):
        for pc in pod_conditions:
            if pc.type == condition_type:
                return pc.status

    def _check_timeout(self, timeout):
        if timeout <= 0:
            LOG.warn(
                'Kubernetes timeout is invalid or unspecified, '
                'using default %ss.', DEFAULT_K8S_TIMEOUT)
            timeout = DEFAULT_K8S_TIMEOUT
        return timeout

    def _watch_job_completion(self, namespace, label_selector, timeout):
        '''
        Watch and wait for job completion.
        Returns when conditions are met, or raises a timeout exception.
        '''
        try:
            timeout = self._check_timeout(timeout)

            ready_jobs = {}
            w = watch.Watch()
            for event in w.stream(
                    self.batch_api.list_namespaced_job,
                    namespace=namespace,
                    label_selector=label_selector,
                    timeout_seconds=timeout):

                job_name = event['object'].metadata.name
                LOG.debug('Watch event %s on job %s', event['type'].upper(),
                          job_name)

                # Track the expected and actual number of completed pods
                # See: https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/  # noqa
                expected = event['object'].spec.completions
                completed = event['object'].status.succeeded

                if expected != completed:
                    ready_jobs[job_name] = False
                else:
                    ready_jobs[job_name] = True
                    LOG.debug(
                        'Job %s complete (spec.completions=%s, '
                        'status.succeeded=%s)', job_name, expected, completed)

                if all(ready_jobs.values()):
                    return True

        except ApiException as e:
            LOG.exception(
                "Exception when watching jobs: namespace=%s, labels=(%s)",
                namespace, label_selector)
            raise e

        if not ready_jobs:
            LOG.warn(
                'Saw no job events for namespace=%s, labels=(%s). '
                'Are the labels correct?', namespace, label_selector)
            return False

        err_msg = ('Reached timeout while waiting for job completions: '
                   'namespace=%s, labels=(%s)' % (namespace, label_selector))
        LOG.error(err_msg)
        raise exceptions.KubernetesWatchTimeoutException(err_msg)
