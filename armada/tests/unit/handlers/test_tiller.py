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

import mock

from armada.exceptions import tiller_exceptions as ex
from armada.handlers import tiller
from armada.utils import helm
from armada.tests.unit import base
from armada.tests.test_utils import AttrDict


class TillerTestCase(base.ArmadaTestCase):
    @mock.patch.object(tiller.Tiller, '_get_tiller_ip')
    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch('armada.handlers.tiller.Config')
    @mock.patch('armada.handlers.tiller.InstallReleaseRequest')
    @mock.patch('armada.handlers.tiller.ReleaseServiceStub')
    def test_install_release(
            self, mock_stub, mock_install_request, mock_config, mock_grpc,
            mock_k8s, mock_ip):
        # instantiate Tiller object
        mock_grpc.insecure_channel.return_value = mock.Mock()
        mock_ip.return_value = '0.0.0.0'
        tiller_obj = tiller.Tiller()
        assert tiller_obj._get_tiller_ip() == '0.0.0.0'

        # set params
        chart = mock.Mock()
        name = None
        namespace = None
        initial_values = None
        updated_values = mock_config(raw=initial_values)
        wait = False
        timeout = 3600

        tiller_obj.install_release(
            chart,
            name,
            namespace,
            values=initial_values,
            wait=wait,
            timeout=timeout)

        mock_stub.assert_called_with(tiller_obj.channel)
        release_request = mock_install_request(
            chart=chart,
            values=updated_values,
            release=name,
            namespace=namespace,
            wait=wait,
            timeout=timeout)
        (
            mock_stub(tiller_obj.channel).InstallRelease.assert_called_with(
                release_request, timeout + 60, metadata=tiller_obj.metadata))

    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch.object(tiller.Tiller, '_get_tiller_port', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_channel(self, mock_grpc, mock_port, mock_ip, _):
        mock_port.return_value = mock.sentinel.port
        mock_ip.return_value = mock.sentinel.ip

        mock_channel = mock.Mock()

        # instantiate Tiller object
        mock_grpc.insecure_channel.return_value = mock_channel
        tiller_obj = tiller.Tiller()

        self.assertIsNotNone(tiller_obj.channel)
        self.assertEqual(mock_channel, tiller_obj.channel)

        mock_grpc.insecure_channel.assert_called_once_with(
            '%s:%s' % (str(mock.sentinel.ip), str(mock.sentinel.port)),
            options=[
                ('grpc.max_send_message_length', tiller.MAX_MESSAGE_LENGTH),
                ('grpc.max_receive_message_length', tiller.MAX_MESSAGE_LENGTH)
            ])

    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_tiller_ip_with_host_provided(self, mock_grpc, _):
        tiller_obj = tiller.Tiller('1.1.1.1')
        self.assertIsNotNone(tiller_obj._get_tiller_ip())
        self.assertEqual('1.1.1.1', tiller_obj._get_tiller_ip())

    @mock.patch.object(tiller.Tiller, '_get_tiller_pod', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_tiller_ip_with_mocked_pod(
            self, mock_grpc, mock_k8s, mock_pod):
        status = mock.Mock(pod_ip='1.1.1.1')
        mock_pod.return_value.status = status
        tiller_obj = tiller.Tiller()
        self.assertEqual('1.1.1.1', tiller_obj._get_tiller_ip())

    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_tiller_pod_throws_exception(
            self, mock_grpc, mock_k8s, mock_ip):

        mock_k8s.get_namespace_pod.return_value.items = []
        tiller_obj = tiller.Tiller()
        mock_grpc.insecure_channel.side_effect = ex.ChannelException()
        self.assertRaises(
            ex.TillerPodNotRunningException, tiller_obj._get_tiller_pod)

    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_tiller_port(self, mock_grpc, _, mock_ip):
        # instantiate Tiller object
        tiller_obj = tiller.Tiller(None, '8080', None)
        self.assertEqual('8080', tiller_obj._get_tiller_port())

    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_tiller_namespace(self, mock_grpc, _, mock_ip):
        # verifies namespace set via instantiation
        tiller_obj = tiller.Tiller(None, None, 'test_namespace2')
        self.assertEqual('test_namespace2', tiller_obj._get_tiller_namespace())

    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_tiller_status_with_ip_provided(self, mock_grpc, _, mock_ip):
        # instantiate Tiller object
        tiller_obj = tiller.Tiller(None, '8080', None)
        self.assertTrue(tiller_obj.tiller_status())

    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    def test_get_tiller_status_no_ip(self, mock_grpc, _, mock_ip):
        mock_ip.return_value = ''
        # instantiate Tiller object
        tiller_obj = tiller.Tiller()
        self.assertFalse(tiller_obj.tiller_status())

    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    @mock.patch('armada.handlers.tiller.ReleaseServiceStub')
    def test_list_releases_empty(self, mock_stub, _, __, mock_ip):
        message_mock = mock.Mock(count=0, total=5, next='', releases=[])
        mock_stub.return_value.ListReleases.return_value = [message_mock]

        # instantiate Tiller object
        tiller_obj = tiller.Tiller()
        self.assertEqual([], tiller_obj.list_releases())

    @mock.patch.object(tiller.Tiller, '_get_tiller_ip', autospec=True)
    @mock.patch('armada.handlers.tiller.K8s', autospec=True)
    @mock.patch('armada.handlers.tiller.grpc', autospec=True)
    @mock.patch('armada.handlers.tiller.ReleaseServiceStub')
    def test_list_charts_empty(self, mock_stub, _, __, mock_ip):
        message_mock = mock.Mock(count=0, total=5, next='', releases=[])
        mock_stub.return_value.ListReleases.return_value = [message_mock]

        # instantiate Tiller object
        tiller_obj = tiller.Tiller()
        self.assertEqual([], tiller_obj.list_charts())

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'ListReleasesRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_list_releases_single_page(
            self, mock_stub, mock_list_releases_request, mock_grpc, _):
        releases = [mock.Mock(), mock.Mock()]
        mock_stub.return_value.ListReleases.return_value = [
            mock.Mock(
                next='',
                count=len(releases),
                total=len(releases),
                releases=releases)
        ]

        tiller_obj = tiller.Tiller('host', '8080', None)
        self.assertEqual(releases, tiller_obj.list_releases())

        mock_stub.assert_called_once_with(tiller_obj.channel)
        mock_stub.return_value.ListReleases.assert_called_once_with(
            mock_list_releases_request.return_value,
            tiller_obj.timeout,
            metadata=tiller_obj.metadata)

        mock_list_releases_request.assert_called_once_with(
            offset="",
            limit=tiller.LIST_RELEASES_PAGE_SIZE,
            status_codes=tiller.const.STATUS_ALL)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'ListReleasesRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_list_releases_returns_latest_only(
            self, mock_stub, mock_list_releases_request, mock_grpc, _):
        latest = mock.Mock(version=3)
        releases = [mock.Mock(version=2), latest, mock.Mock(version=1)]
        for r in releases:
            r.name = 'test'
        mock_stub.return_value.ListReleases.return_value = [
            mock.Mock(
                next='',
                count=len(releases),
                total=len(releases),
                releases=releases)
        ]

        tiller_obj = tiller.Tiller('host', '8080', None)
        self.assertEqual([latest], tiller_obj.list_releases())

        mock_stub.assert_called_once_with(tiller_obj.channel)
        mock_stub.return_value.ListReleases.assert_called_once_with(
            mock_list_releases_request.return_value,
            tiller_obj.timeout,
            metadata=tiller_obj.metadata)

        mock_list_releases_request.assert_called_once_with(
            offset="",
            limit=tiller.LIST_RELEASES_PAGE_SIZE,
            status_codes=tiller.const.STATUS_ALL)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'ListReleasesRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_list_releases_paged(
            self, mock_stub, mock_list_releases_request, mock_grpc, _):
        page_count = 3
        release_count = tiller.LIST_RELEASES_PAGE_SIZE * page_count
        releases = [mock.Mock() for i in range(release_count)]
        for i, release in enumerate(releases):
            release.name = mock.PropertyMock(return_value=str(i))
        pages = [
            [
                mock.Mock(
                    count=release_count,
                    total=release_count + 5,
                    next='' if i == page_count - 1 else str(
                        (tiller.LIST_RELEASES_PAGE_SIZE * (i + 1))),
                    releases=releases[tiller.LIST_RELEASES_PAGE_SIZE
                                      * i:tiller.LIST_RELEASES_PAGE_SIZE
                                      * (i + 1)])
            ] for i in range(page_count)
        ]
        mock_stub.return_value.ListReleases.side_effect = pages

        mock_list_releases_side_effect = [
            mock.Mock() for i in range(page_count)
        ]
        mock_list_releases_request.side_effect = mock_list_releases_side_effect

        tiller_obj = tiller.Tiller('host', '8080', None)
        self.assertEqual(releases, tiller_obj.list_releases())

        mock_stub.assert_called_once_with(tiller_obj.channel)

        list_releases_calls = [
            mock.call(
                mock_list_releases_side_effect[i],
                tiller_obj.timeout,
                metadata=tiller_obj.metadata) for i in range(page_count)
        ]
        mock_stub.return_value.ListReleases.assert_has_calls(
            list_releases_calls)

        list_release_request_calls = [
            mock.call(
                offset='' if i == 0 else str(
                    tiller.LIST_RELEASES_PAGE_SIZE * i),
                limit=tiller.LIST_RELEASES_PAGE_SIZE,
                status_codes=tiller.const.STATUS_ALL)
            for i in range(page_count)
        ]
        mock_list_releases_request.assert_has_calls(list_release_request_calls)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'GetReleaseContentRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_get_release_content(
            self, mock_release_service_stub, mock_release_content_request,
            mock_grpc, _):
        mock_release_service_stub.return_value.GetReleaseContent\
            .return_value = {}

        tiller_obj = tiller.Tiller('host', '8080', None)

        self.assertEqual({}, tiller_obj.get_release_content('release'))
        get_release_content_stub = mock_release_service_stub. \
            return_value.GetReleaseContent
        get_release_content_stub.assert_called_once_with(
            mock_release_content_request.return_value,
            tiller_obj.timeout,
            metadata=tiller_obj.metadata)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'GetVersionRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_tiller_version(
            self, mock_release_service_stub, mock_version_request, mock_grpc,
            _):

        mock_version = mock.Mock()
        mock_version.Version.sem_ver = mock.sentinel.sem_ver
        mock_release_service_stub.return_value.GetVersion\
            .return_value = mock_version

        tiller_obj = tiller.Tiller('host', '8080', None)

        self.assertEqual(mock.sentinel.sem_ver, tiller_obj.tiller_version())

        mock_release_service_stub.assert_called_once_with(tiller_obj.channel)

        get_version_stub = mock_release_service_stub.return_value.GetVersion
        get_version_stub.assert_called_once_with(
            mock_version_request.return_value,
            tiller_obj.timeout,
            metadata=tiller_obj.metadata)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'GetVersionRequest')
    @mock.patch.object(tiller, 'GetReleaseStatusRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_get_release_status(
            self, mock_release_service_stub, mock_rel_status_request,
            mock_version_request, mock_grpc, _):
        mock_release_service_stub.return_value.GetReleaseStatus. \
            return_value = {}

        tiller_obj = tiller.Tiller('host', '8080', None)
        self.assertEqual({}, tiller_obj.get_release_status('release'))

        mock_release_service_stub.assert_called_once_with(tiller_obj.channel)
        get_release_status_stub = mock_release_service_stub.return_value. \
            GetReleaseStatus
        get_release_status_stub.assert_called_once_with(
            mock_rel_status_request.return_value,
            tiller_obj.timeout,
            metadata=tiller_obj.metadata)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'UninstallReleaseRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_uninstall_release(
            self, mock_release_service_stub, mock_uninstall_release_request,
            mock_grpc, _):
        mock_release_service_stub.return_value.UninstallRelease\
            .return_value = {}

        tiller_obj = tiller.Tiller('host', '8080', None)

        self.assertEqual({}, tiller_obj.uninstall_release('release'))

        mock_release_service_stub.assert_called_once_with(tiller_obj.channel)
        uninstall_release_stub = mock_release_service_stub.return_value. \
            UninstallRelease

        uninstall_release_stub.assert_called_once_with(
            mock_uninstall_release_request.return_value,
            tiller_obj.timeout,
            metadata=tiller_obj.metadata)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch.object(tiller, 'RollbackReleaseRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_rollback_release(
            self, mock_release_service_stub, mock_rollback_release_request, _,
            __):
        mock_release_service_stub.return_value.RollbackRelease\
            .return_value = {}

        tiller_obj = tiller.Tiller('host', '8080', None)

        release = 'release'
        version = 0
        wait = True
        timeout = 123
        recreate_pods = True
        force = True

        self.assertIsNone(
            tiller_obj.rollback_release(
                release,
                version,
                wait=wait,
                timeout=timeout,
                force=force,
                recreate_pods=recreate_pods))

        mock_rollback_release_request.assert_called_once_with(
            name=release,
            version=version,
            wait=wait,
            timeout=timeout,
            force=force,
            recreate=recreate_pods)

        mock_release_service_stub.assert_called_once_with(tiller_obj.channel)
        rollback_release_stub = mock_release_service_stub.return_value. \
            RollbackRelease

        rollback_release_stub.assert_called_once_with(
            mock_rollback_release_request.return_value,
            timeout + tiller.GRPC_EPSILON,
            metadata=tiller_obj.metadata)

    @mock.patch('armada.handlers.tiller.K8s')
    @mock.patch('armada.handlers.tiller.grpc')
    @mock.patch('armada.handlers.tiller.Config')
    @mock.patch.object(tiller, 'UpdateReleaseRequest')
    @mock.patch.object(tiller, 'ReleaseServiceStub')
    def test_update_release(
            self, mock_release_service_stub, mock_update_release_request,
            mock_config, _, __):
        release = 'release'
        chart = {}
        namespace = 'namespace'
        code = 0
        status = 'DEPLOYED'
        description = 'desc'
        version = 2
        values = mock_config(raw=None)
        mock_release_service_stub.return_value.UpdateRelease.return_value =\
            AttrDict(**{
                'release': AttrDict(**{
                    'name': release,
                    'namespace': namespace,
                    'info': AttrDict(**{
                        'status': AttrDict(**{
                            'Code': AttrDict(**{
                                'Name': lambda c:
                                    status if c == code else None
                            }),
                            'code': code
                        }),
                        'Description': description
                    }),
                    'version': version
                })
            })

        tiller_obj = tiller.Tiller('host', '8080', None)

        disable_hooks = False
        wait = True
        timeout = 123
        force = True
        recreate_pods = True

        result = tiller_obj.update_release(
            chart,
            release,
            namespace,
            disable_hooks=disable_hooks,
            values=values,
            wait=wait,
            timeout=timeout,
            force=force,
            recreate_pods=recreate_pods)

        mock_update_release_request.assert_called_once_with(
            chart=chart,
            name=release,
            disable_hooks=False,
            values=values,
            wait=wait,
            timeout=timeout,
            force=force,
            recreate=recreate_pods)

        mock_release_service_stub.assert_called_once_with(tiller_obj.channel)
        update_release_stub = mock_release_service_stub.return_value. \
            UpdateRelease

        update_release_stub.assert_called_once_with(
            mock_update_release_request.return_value,
            timeout + tiller.GRPC_EPSILON,
            metadata=tiller_obj.metadata)

        expected_result = tiller.TillerResult(
            release, namespace, status, description, version)

        self.assertEqual(expected_result, result)

    def _test_test_release(self, grpc_response_mock):
        @mock.patch('armada.handlers.tiller.K8s')
        @mock.patch('armada.handlers.tiller.grpc')
        @mock.patch('armada.handlers.tiller.Config')
        @mock.patch.object(tiller, 'TestReleaseRequest')
        @mock.patch.object(tiller, 'ReleaseServiceStub')
        def do_test(
                self, mock_release_service_stub, mock_test_release_request,
                mock_config, _, __):
            tiller_obj = tiller.Tiller('host', '8080', None)
            release = 'release'
            test_suite_run = {}

            mock_release_service_stub.return_value.RunReleaseTest\
                .return_value = grpc_response_mock

            tiller_obj.get_release_status = mock.Mock()
            tiller_obj.get_release_status.return_value = AttrDict(
                **{
                    'info': AttrDict(
                        **{
                            'status': AttrDict(
                                **{'last_test_suite_run': test_suite_run}),
                            'Description': 'Failed'
                        })
                })

            result = tiller_obj.test_release(release)

            self.assertEqual(test_suite_run, result)

        do_test(self)

    def test_test_release_no_tests(self):
        self._test_test_release(
            [
                AttrDict(
                    **{
                        'msg': 'No Tests Found',
                        'status': helm.TESTRUN_STATUS_UNKNOWN
                    })
            ])

    def test_test_release_success(self):
        self._test_test_release(
            [
                AttrDict(
                    **{
                        'msg': 'RUNNING: ...',
                        'status': helm.TESTRUN_STATUS_RUNNING
                    }),
                AttrDict(
                    **{
                        'msg': 'SUCCESS: ...',
                        'status': helm.TESTRUN_STATUS_SUCCESS
                    })
            ])

    def test_test_release_failure(self):
        self._test_test_release(
            [
                AttrDict(
                    **{
                        'msg': 'RUNNING: ...',
                        'status': helm.TESTRUN_STATUS_RUNNING
                    }),
                AttrDict(
                    **{
                        'msg': 'FAILURE: ...',
                        'status': helm.TESTRUN_STATUS_FAILURE
                    })
            ])

    def test_test_release_failure_to_run(self):
        class Iterator:
            def __iter__(self):
                return self

            def __next__(self):
                raise Exception

        def test():
            self._test_test_release(Iterator())

        self.assertRaises(ex.ReleaseException, test)
