# Copyright 2019, AT&T Intellectual Property
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
from datetime import datetime

from kubernetes.client.rest import ApiException
import mock
import testtools

from armada.handlers import lock


@mock.patch('armada.handlers.lock.K8s')
@mock.patch.object(lock.time, 'sleep', lambda x: True)
class LockTestCase(testtools.TestCase):
    def __init__(self, *args, **kwargs):
        super(LockTestCase, self).__init__(*args, **kwargs)
        self.resp = None
        self.test_lock = None
        self.mock_create = None
        self.mock_read = None
        self.mock_delete = None
        self.mock_replace = None
        self.mock_create_crd = None

    def setUp(self):
        super(LockTestCase, self).setUp()
        self_link = "/apis/armada.tiller/v1/namespaces/default/locks/"\
                    "locks.armada.tiller.test"
        self.resp = {
            'apiVersion': "armada.tiller/v1",
            'data': {
                'lastUpdated': "2019-01-22T16:20:14Z"
            },
            'metadata': {
                'resourceVersion': "95961",
                'generation': 1,
                'name': "locks.armada.process.test",
                'creationTimestamp': "2019-01-22T16:20:14Z",
                'uid': "9930c9a0-1e61-11e9-9e5a-0800276b7c7d",
                'clusterName': "",
                'namespace': "default",
                'selfLink': self_link
            },
            'kind': "Resource"
        }
        with mock.patch("armada.handlers.lock.K8s"):
            self.test_lock = lock.Lock("test")
            self.test_lock.timeout = 1
            self.test_lock.acquire_delay = 0.1
            self.test_lock.expire_time = 10

            # Mocking the methods of self.k8s for the LockConfig
            mock_k8s = self.test_lock.lock_config.k8s = mock.Mock()
            self.mock_create = mock_k8s.create_custom_resource = mock.Mock()
            self.mock_read = mock_k8s.read_custom_resource = mock.Mock()
            self.mock_delete = mock_k8s.delete_custom_resource = mock.Mock()
            self.mock_replace = mock_k8s.replace_custom_resource = mock.Mock()
            self.mock_create_crd = mock_k8s.create_custom_resource_definition \
                = mock.Mock()

    def test_get_lock(self, _):
        try:
            # read needs to raise a 404 when the lock doesn't exist
            self.mock_read.side_effect = ApiException(status=404)
            mock_read = self.mock_read
            resp = self.resp

            def update_get_and_set_return(*args, **kwargs):
                # Once the lock is 'created' it should no longer raise err
                mock_read.read_custom_resource.side_effect = None
                mock_read.read_custom_resource.return_value = resp
                # Set the mock_create return to return the new lock
                return resp

            self.mock_create.side_effect = update_get_and_set_return

            self.test_lock.acquire_lock()
        except lock.LockException:
            self.fail("acquire_lock() raised LockException unexpectedly")
        except ApiException:
            self.fail("acquire_lock() raised ApiException unexpectedly")
        try:
            self.test_lock.release_lock()
        except lock.LockException:
            self.fail("release_lock() raised LockException unexpectedly")
        except ApiException:
            self.fail("acquire_lock() raised ApiException unexpectedly")

    @mock.patch('armada.handlers.lock.time', autospec=True)
    def test_timeout_getting_lock(self, mock_time, _):
        # The timestamp on the 'lock' will be new to avoid expiring
        last_update = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        self.resp['data']['lastUpdated'] = str(last_update)
        # Mocking time.time() so that acquire_lock() is run through once, and
        # once the time is checked again the timeout will be reached
        test_time = 1550510151.792119
        mock_time.time = mock.Mock()

        def set_time():
            nonlocal test_time
            test_time += self.test_lock.timeout / 2
            return test_time

        mock_time.time.side_effect = set_time

        # Creating large expire time so the lock doesn't get overwritten
        self.test_lock.expire_time = 60
        # Updating mocks so that there is always a 'lock'
        self.mock_create.side_effect = ApiException(status=409)
        self.mock_read.return_value = self.resp

        # It should fail to acquire the lock before the attempt times out
        self.assertRaises(lock.LockException, self.test_lock.acquire_lock)

    def test_lock_expiration(self, _):
        # Timestamp on the 'lock' is old to ensure lock is expired
        self.resp['data']['lastUpdated'] = "2018-01-22T16:20:14Z"

        # When the lock already exists, Kubernetes responds with a 409
        self.mock_create.side_effect = ApiException(status=409)
        # Getting the lock should return the 'lock' above
        self.mock_read.return_value = self.resp

        # New return value of create should have a newer timestamp
        new_resp = copy.deepcopy(self.resp)
        new_time = str(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))
        new_resp['metadata']['creationTimestamp'] = new_time
        mock_create = self.mock_create

        def clear_side_effect(*args, **kwargs):
            mock_create.side_effect = None
            mock_create.return_value = new_resp

        # Once the lock is 'deleted' we need to stop create from raising err
        self.mock_delete.side_effect = clear_side_effect

        try:
            self.test_lock.acquire_lock()
        except lock.LockException:
            self.fail("acquire_lock() raised LockException unexpectedly")

    def test_custom_resource_definition_creation(self, _):
        # When the crd doesn't exist yet, Kubernetes responds with a 404 when
        # trying to create a lock
        self.mock_create.side_effect = ApiException(status=404)
        mock_create = self.mock_create
        resp = self.resp

        def clear_side_effect(*args, **kwargs):
            mock_create.side_effect = None
            mock_create.return_value = resp

        # Once the definition is 'created' we need to stop raising err
        self.mock_create_crd.side_effect = clear_side_effect

        try:
            self.test_lock.acquire_lock()
        except lock.LockException:
            self.fail("acquire_lock() raised LockException unexpectedly")

    @mock.patch.object(lock.CONF, "lock_update_interval", 0.1)
    @mock.patch('armada.handlers.lock.ThreadPoolExecutor')
    @mock.patch('armada.handlers.lock.time', autospec=True)
    def test_lock_decorator(self, mock_time, mock_thread, _):
        # read needs to raise a 404 when the lock doesn't exist
        self.mock_read.side_effect = ApiException(status=404)
        mock_read = self.mock_read
        resp = self.resp

        def update_get_and_set_return(*args, **kwargs):
            # Once the lock is 'created' it should no longer raise err
            mock_read.read_custom_resource.side_effect = None
            mock_read.read_custom_resource.return_value = resp
            # Set the mock_create return to return the new lock
            return resp

        self.mock_create.side_effect = update_get_and_set_return
        self.mock_replace.return_value = self.resp

        # Mocking the threading in lock_and_thread
        mock_pool = mock_thread.return_value = mock.Mock()
        mock_pool.submit = mock.Mock()
        mock_future = mock_pool.submit.return_value = mock.Mock()
        mock_future.done = mock.Mock()
        # future.done() needs to return false so lock.update_lock() gets called
        mock_future.done.return_value = False

        def clear_done():
            mock_future.done.return_value = True
            mock_future.done.side_effect = None

        # After future.done() is called once it can be cleared and return True
        mock_future.done.side_effect = clear_done

        # Mocking time.time() so it appears that more time has passed than
        # CONF.lock_update_interval so update_lock() is run
        # This also affects the acquire_lock() timeout check, which is why
        # the lock_update_interval is mocked to be a low number
        test_time = 1550510151.792119
        mock_time.time = mock.Mock()

        def set_time():
            nonlocal test_time
            test_time += lock.CONF.lock_update_interval + 1
            return test_time

        mock_time.time.side_effect = set_time

        def func():
            return

        test_func_dec = lock.lock_and_thread()(func)
        test_func_dec.lock = self.test_lock
        try:
            test_func_dec()
        except lock.LockException:
            self.fail("acquire_lock() raised LockException unexpectedly")
        except ApiException:
            self.fail("acquire_lock() raised ApiException unexpectedly")
