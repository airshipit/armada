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

from oslo_log import log as logging

from armada.conf import get_current_chart
from armada.exceptions import armada_exceptions as ex
from armada.handlers import helm
from armada.handlers import schema
from armada.utils.release import label_selectors

LOG = logging.getLogger(__name__)


class PreUpdateActions():
    def __init__(self, k8s):
        self.k8s = k8s

    def execute(
            self, actions, release_name, namespace, chart, disable_hooks,
            values, timeout):
        '''
        :param actions: array of items actions
        :param namespace: name of pod for actions
        '''

        # TODO: Remove when v1 doc support is removed.
        try:
            for action in actions.get('update', []):
                name = action.get('name')
                LOG.info('Updating %s ', name)
                action_type = action.get('type')
                labels = action.get('labels')

                self.rolling_upgrade_pod_deployment(
                    name, release_name, namespace, labels, action_type, chart,
                    disable_hooks, values, timeout)
        except Exception:
            LOG.exception(
                "Pre-action failure: could not perform rolling upgrade for "
                "%(res_type)s %(res_name)s.", {
                    'res_type': action_type,
                    'res_name': name
                })
            raise ex.PreUpdateJobDeleteException(name, namespace)

        try:
            for action in actions.get('delete', []):
                name = action.get('name')
                action_type = action.get('type')
                labels = action.get('labels', None)

                self.delete_resources(
                    action_type, labels, namespace, timeout=timeout)
        except Exception:
            LOG.exception(
                "Pre-action failure: could not delete %(res_type)s "
                "%(res_name)s.", {
                    'res_type': action_type,
                    'res_name': name
                })
            raise ex.PreUpdateJobDeleteException(name, namespace)

    def delete_resources(
            self,
            resource_type,
            resource_labels,
            namespace,
            wait=False,
            timeout=helm.DEFAULT_HELM_TIMEOUT):
        '''
        Delete resources matching provided resource type, labels, and
        namespace.

        :param resource_type: type of resource e.g. job, pod, etc.
        :param resource_labels: labels for selecting the resources
        :param namespace: namespace of resources
        '''
        timeout = self._check_timeout(wait, timeout)

        label_selector = ''
        if resource_labels is not None:
            label_selector = label_selectors(resource_labels)
        LOG.debug(
            "Deleting resources in namespace: %s, matching "
            "selectors: %s (timeout=%s).", namespace, label_selector, timeout)

        handled = False
        if resource_type == 'job':
            get_jobs = self.k8s.get_namespace_job(
                namespace, label_selector=label_selector)
            for jb in get_jobs.items:
                jb_name = jb.metadata.name

                LOG.info(
                    "Deleting job: %s in namespace: %s", jb_name, namespace)
                self.k8s.delete_job_action(jb_name, namespace, timeout=timeout)
            handled = True

        # TODO: Remove when v1 doc support is removed.
        chart = get_current_chart()
        schema_info = schema.get_schema_info(chart['schema'])
        job_implies_cronjob = schema_info.version < 2
        implied_cronjob = resource_type == 'job' and job_implies_cronjob

        if resource_type == 'cronjob' or implied_cronjob:
            get_jobs = self.k8s.get_namespace_cron_job(
                namespace, label_selector=label_selector)
            for jb in get_jobs.items:
                jb_name = jb.metadata.name

                # TODO: Remove when v1 doc support is removed.
                if implied_cronjob:
                    LOG.warn(
                        "Deleting cronjobs via `type: job` is "
                        "deprecated, use `type: cronjob` instead")

                LOG.info(
                    "Deleting cronjob %s in namespace: %s", jb_name, namespace)
                self.k8s.delete_cron_job_action(jb_name, namespace)
            handled = True

        if resource_type == 'pod':
            release_pods = self.k8s.get_namespace_pod(
                namespace, label_selector=label_selector)
            for pod in release_pods.items:
                pod_name = pod.metadata.name

                LOG.info(
                    "Deleting pod %s in namespace: %s", pod_name, namespace)
                self.k8s.delete_pod_action(pod_name, namespace)
                if wait:
                    self.k8s.wait_for_pod_redeployment(pod_name, namespace)
            handled = True

        if not handled:
            LOG.error(
                'No resources found with labels=%s type=%s namespace=%s',
                resource_labels, resource_type, namespace)

    def rolling_upgrade_pod_deployment(
            self,
            name,
            release_name,
            namespace,
            resource_labels,
            action_type,
            chart,
            disable_hooks,
            values,
            timeout=helm.DEFAULT_HELM_TIMEOUT):
        '''
        update statefulsets (daemon, stateful)
        '''

        if action_type == 'daemonset':

            LOG.info('Updating: %s', action_type)

            label_selector = ''

            if resource_labels is not None:
                label_selector = label_selectors(resource_labels)

            get_daemonset = self.k8s.get_namespace_daemon_set(
                namespace, label_selector=label_selector)

            for ds in get_daemonset.items:
                ds_name = ds.metadata.name
                ds_labels = ds.metadata.labels
                if ds_name == name:
                    LOG.info(
                        "Deleting %s : %s in %s", action_type, ds_name,
                        namespace)
                    self.k8s.delete_daemon_action(ds_name, namespace)

                    # update the daemonset yaml
                    template = self.get_chart_templates(
                        ds_name, name, release_name, namespace, chart,
                        disable_hooks, values)
                    template['metadata']['labels'] = ds_labels
                    template['spec']['template']['metadata'][
                        'labels'] = ds_labels

                    self.k8s.create_daemon_action(
                        namespace=namespace, template=template)

                    # delete pods
                    self.delete_resources(
                        'pod',
                        resource_labels,
                        namespace,
                        wait=True,
                        timeout=timeout)

        else:
            LOG.error("Unable to exectue name: % type: %s", name, action_type)

    def _check_timeout(self, wait, timeout):
        if timeout is None or timeout <= 0:
            if wait:
                LOG.warn(
                    'Pre-update actions timeout is invalid or unspecified, '
                    'using default %ss.', self.timeout)
            timeout = self.timeout
        return timeout
