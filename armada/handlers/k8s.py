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

from kubernetes import client
from kubernetes import config
from kubernetes import watch
from kubernetes.client.rest import ApiException
from oslo_config import cfg
from oslo_log import log as logging

from armada.const import DEFAULT_K8S_TIMEOUT
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
        self.apps_v1_api = client.AppsV1Api()

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

    def get_namespace_job(self, namespace="default", **kwargs):
        '''
        :param label_selector: labels of the jobs
        :param namespace: namespace of the jobs
        '''

        try:
            return self.batch_api.list_namespaced_job(namespace, **kwargs)
        except ApiException as e:
            LOG.error("Exception getting jobs: namespace=%s, label=%s: %s",
                      namespace, kwargs.get('label_selector', ''), e)

    def get_namespace_cron_job(self, namespace="default", **kwargs):
        '''
        :param label_selector: labels of the cron jobs
        :param namespace: namespace of the cron jobs
        '''

        try:
            return self.batch_v1beta1_api.list_namespaced_cron_job(
                namespace, **kwargs)
        except ApiException as e:
            LOG.error(
                "Exception getting cron jobs: namespace=%s, label=%s: %s",
                namespace, kwargs.get('label_selector', ''), e)

    def get_namespace_pod(self, namespace="default", **kwargs):
        '''
        :param namespace: namespace of the Pod
        :param label_selector: filters Pods by label

        This will return a list of objects req namespace
        '''

        return self.client.list_namespaced_pod(namespace, **kwargs)

    def get_namespace_deployment(self, namespace='default', **kwargs):
        '''
        :param namespace: namespace of target deamonset
        :param labels: specify targeted deployment
        '''
        return self.apps_v1_api.list_namespaced_deployment(namespace, **kwargs)

    def get_namespace_stateful_set(self, namespace='default', **kwargs):
        '''
        :param namespace: namespace of target stateful set
        :param labels: specify targeted stateful set
        '''
        return self.apps_v1_api.list_namespaced_stateful_set(
            namespace, **kwargs)

    def get_namespace_daemon_set(self, namespace='default', **kwargs):
        '''
        :param namespace: namespace of target deamonset
        :param labels: specify targeted daemonset
        '''
        return self.apps_v1_api.list_namespaced_daemon_set(namespace, **kwargs)

    def create_daemon_action(self, namespace, template):
        '''
        :param: namespace - pod namespace
        :param: template - deploy daemonset via yaml
        '''
        # we might need to load something here

        self.apps_v1_api.create_namespaced_daemon_set(namespace, body=template)

    def delete_daemon_action(self, name, namespace="default", body=None):
        '''
        :param: namespace - pod namespace

        This will delete daemonset
        '''

        if body is None:
            body = client.V1DeleteOptions()

        return self.apps_v1_api.delete_namespaced_daemon_set(
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
            resource_name = event['object'].metadata.name

            if release in resource_name:
                found_events = True
                pod_state = event['object'].status.phase
                if pod_state == 'Succeeded':
                    w.stop()
                    break

        if not found_events:
            LOG.warn('Saw no test events for release %s', release)

    def _check_timeout(self, timeout):
        if timeout <= 0:
            LOG.warn(
                'Kubernetes timeout is invalid or unspecified, '
                'using default %ss.', DEFAULT_K8S_TIMEOUT)
            timeout = DEFAULT_K8S_TIMEOUT
        return timeout
