# Copyright 2017 Hewlett Packard Enterprise Development LP.
# Copyright 2017 Universidade Federal de Campina Grande
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy
import mock

from neutron.tests import base
from oslo_service import loopingcall

from networking_oneview.ml2.drivers.oneview import common
from networking_oneview.ml2.drivers.oneview import database_manager
from networking_oneview.ml2.drivers.oneview.synchronization import \
    Synchronization as sync
from networking_oneview.tests.unit.ml2.drivers.oneview import \
    test_oneview_mech_driver as mech_test


class SynchronizationTestCase(base.BaseTestCase):
    def setUp(self):
        super(SynchronizationTestCase, self).setUp()
        oneview_client = mock.MagicMock()
        neutron_oneview_client = mock.MagicMock()
        flat_net_mappings = mech_test.FLAT_NET_MAPPINGS
        self.sync = sync(
            oneview_client=oneview_client,
            neutron_oneview_client=neutron_oneview_client,
            flat_net_mappings=flat_net_mappings)

    @mock.patch.object(loopingcall, 'FixedIntervalLoopingCall')
    def test_start(self, mock_loop):
        self.sync.start()
        heartbeat = mock_loop.return_value
        mock_loop.assert_called_with(self.sync.synchronize)
        self.assertTrue(heartbeat.start.called)

    @mock.patch.object(sync, 'recreate_connection')
    @mock.patch.object(sync, 'synchronize_uplinkset_from_mapped_networks')
    @mock.patch.object(sync, 'delete_unmapped_oneview_networks')
    @mock.patch.object(sync, 'create_oneview_networks_from_neutron')
    def test_synchronize(
        self, mock_create_networks, mock_delete_unmapped,
        mock_synchronize_uplinkset, mock_recreate_connection
    ):
        self.sync.synchronize()

        self.assertTrue(mock_create_networks.called)
        self.assertFalse(mock_delete_unmapped.called)
        self.assertFalse(mock_synchronize_uplinkset.called)
        self.assertFalse(mock_recreate_connection.called)

    @mock.patch.object(sync, 'recreate_connection')
    @mock.patch.object(sync, 'synchronize_uplinkset_from_mapped_networks')
    @mock.patch.object(sync, 'delete_unmapped_oneview_networks')
    @mock.patch.object(sync, 'create_oneview_networks_from_neutron')
    def test_synchronize_with_force_sync_delete(
        self, mock_create_networks, mock_delete_unmapped,
        mock_synchronize_uplinkset, mock_recreate_connection
    ):
        common.CONF.DEFAULT.force_sync_delete_ops = True
        self.sync.synchronize()

        self.assertTrue(mock_create_networks.called)
        self.assertTrue(mock_delete_unmapped.called)
        self.assertTrue(mock_synchronize_uplinkset.called)
        self.assertTrue(mock_recreate_connection.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_oneview_network_lig')
    @mock.patch.object(database_manager,
                       'list_networks_and_segments_with_physnet')
    @mock.patch.object(common, 'get_database_session')
    def test_create_oneview_networks_from_neutron(
            self, mock_session, mock_phys_net, mock_del_lig, mock_del_net,
            mock_get_net):
        session = mock_session()
        client = self.sync.oneview_client
        client.ethernet_networks.get.return_value = True
        mock_get_net.return_value = None

        mock_phys_net.return_value = [[
            {'id': '123'},
            {'physical_network': 'physnet',
             'network_type': 'vlan',
             'segmentation_id': '321'}
        ]]
        network_dict = {
            'provider:physical_network': 'physnet',
            'provider:network_type': 'vlan',
            'provider:segmentation_id': '321',
            'id': '123',
        }

        self.sync.create_oneview_networks_from_neutron()

        self.assertFalse(mock_del_net.called)
        self.assertFalse(mock_del_lig.called)
        self.sync.neutron_client.network.create.assert_called_with(
            session, network_dict
        )

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_oneview_network_lig')
    @mock.patch.object(database_manager,
                       'list_networks_and_segments_with_physnet')
    @mock.patch.object(common, 'get_database_session')
    def test_create_oneview_networks_from_neutron_inconsistent(
            self, mock_session, mock_phys_net, mock_del_lig, mock_del_net,
            mock_get_net):
        client = self.sync.oneview_client
        client.ethernet_networks.get.return_value = None
        mock_phys_net.return_value = [[
            {'id': '123'},
            {'physical_network': 'physnet',
             'network_type': 'vlan',
             'segmentation_id': '321'}
        ]]

        self.sync.create_oneview_networks_from_neutron()

        self.assertTrue(mock_del_net.called)
        self.assertTrue(mock_del_lig.called)

    @mock.patch.object(database_manager, 'get_neutron_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    @mock.patch.object(common, 'get_database_session')
    def test_delete_unmapped_oneview_networks(self, mock_session,
                                              mock_segment, mock_network):
        client = self.sync.oneview_client
        client.ethernet_networks.get_all.return_value = [{
            'name': 'Neutron [123]',
            'uri': '/fake_net_uri/1234'
        }]
        self.sync.neutron_client.network.is_uplinkset_mapping.return_value = 1

        self.sync.delete_unmapped_oneview_networks()

        self.assertFalse(client.ethernet_networks.delete.called)
        self.assertFalse(self.sync.neutron_client.network.delete.called)

    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_oneview_network_lig')
    @mock.patch.object(database_manager, 'get_neutron_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    @mock.patch.object(common, 'get_database_session')
    def test_delete_unmapped_oneview_networks_no_net(
            self, mock_session, mock_segment, mock_network,
            mock_del_lig, mock_del_net):
        session = mock_session()
        client = self.sync.oneview_client
        client.ethernet_networks.get_all.return_value = [{
            'name': 'Neutron [123]',
            'uri': '/fake_net_uri/1234'
        }]
        mock_network.return_value = None
        self.sync.neutron_client.network.is_uplinkset_mapping.return_value = 1

        self.sync.delete_unmapped_oneview_networks()

        mock_del_net.assert_called_with(session, neutron_network_id='123')
        mock_del_lig.assert_called_with(session, oneview_network_id='1234')
        client.ethernet_networks.delete.assert_called_with('1234')
        self.assertFalse(self.sync.neutron_client.network.delete.called)

    @mock.patch.object(database_manager, 'get_neutron_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    @mock.patch.object(sync, '_delete_connections')
    @mock.patch.object(common, 'get_database_session')
    def test_delete_unmapped_oneview_networks_not_mapped(
            self, mock_session, mock_del_conn, mock_segment, mock_network):
        session = mock_session()
        client = self.sync.oneview_client
        client.ethernet_networks.get_all.return_value = [{
            'name': 'Neutron [123]',
            'uri': '/fake_net_uri/1234'
        }]
        self.sync.neutron_client.network.is_uplinkset_mapping.return_value = 0

        self.sync.delete_unmapped_oneview_networks()

        self.assertFalse(client.ethernet_networks.delete.called)
        mock_del_conn.assert_called_with('123')
        self.sync.neutron_client.network.delete.assert_called_with(
            session, {'id': '123'}
        )

    @mock.patch.object(database_manager, 'list_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    @mock.patch.object(common, 'get_database_session')
    def test_synchronize_uplinkset_from_mapped_networks(
            self, mock_session, mock_segment, mock_list_net):
        session = mock_session()
        fake_network = mech_test.FakeNetwork()
        mock_list_net.return_value = [fake_network]
        mock_segment.return_value = {
            'network_type': 'flat',
            'physical_network': 'physnet'
        }

        self.sync.synchronize_uplinkset_from_mapped_networks()

        self.sync.neutron_client.network.update_network_lig.assert_called_with(
            session, fake_network.oneview_network_id, 'flat', 'physnet'
        )

    @mock.patch.object(database_manager, 'list_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    @mock.patch.object(common, 'get_database_session')
    def test_synchronize_uplinkset_from_mapped_networks_no_segment(
            self, mock_session, mock_segment, mock_list_net):
        fake_network = mech_test.FakeNetwork()
        mock_list_net.return_value = [fake_network]
        mock_segment.return_value = None

        self.sync.synchronize_uplinkset_from_mapped_networks()

        self.assertFalse(
            self.sync.neutron_client.network.update_network_lig.called
        )

    @mock.patch.object(database_manager, 'get_port_with_binding_profile')
    @mock.patch.object(database_manager, 'list_neutron_oneview_network')
    @mock.patch.object(
        common, 'server_hardware_from_local_link_information_list')
    @mock.patch.object(common, 'local_link_information_from_port')
    @mock.patch.object(sync, '_update_connection')
    @mock.patch.object(sync, '_fix_connections_with_removed_networks')
    @mock.patch.object(common, 'get_database_session')
    def test_recreate_connection(
            self, mock_session, mock_fix_sp, mock_update,
            mock_lli, mock_sh, mock_list_net, mock_port):
        client = self.sync.neutron_client
        mock_port.return_value = [[
            {'network_id': '123',
             'mac_address': 'aa:11:cc:33:ee:44'},
            {'vnic_type': 'baremetal',
             'profile': '1111'}
        ]]
        fake_network = mech_test.FakeNetwork()
        mock_list_net.return_value = [fake_network]
        server_profile = copy.deepcopy(mech_test.FAKE_SERVER_PROFILE)
        server_profile['connections'][0]['networkUri'] = (
            '/rest/ethernet-networks/' + fake_network.oneview_network_id
        )
        client.port.server_profile_from_server_hardware.return_value = (
            server_profile
        )

        self.sync.recreate_connection()

        mock_fix_sp.assert_called_with(server_profile)
        self.assertFalse(mock_update.called)
        self.assertFalse(self.sync.neutron_client.port.create.called)

    @mock.patch.object(database_manager, 'get_port_with_binding_profile')
    @mock.patch.object(database_manager, 'list_neutron_oneview_network')
    @mock.patch.object(
        common, 'server_hardware_from_local_link_information_list')
    @mock.patch.object(common, 'local_link_information_from_port')
    @mock.patch.object(sync, '_update_connection')
    @mock.patch.object(sync, '_fix_connections_with_removed_networks')
    @mock.patch.object(common, 'get_database_session')
    def test_recreate_connection_different_network(
            self, mock_session, mock_fix_sp, mock_update,
            mock_lli, mock_sh, mock_list_net, mock_port):
        client = self.sync.neutron_client
        mock_port.return_value = [[
            {'network_id': '123',
             'mac_address': 'aa:11:cc:33:ee:44'},
            {'vnic_type': 'baremetal',
             'profile': '1111'}
        ]]
        fake_network = mech_test.FakeNetwork()
        mock_list_net.return_value = [fake_network]
        server_profile = copy.deepcopy(mech_test.FAKE_SERVER_PROFILE)
        client.port.server_profile_from_server_hardware.return_value = (
            server_profile
        )

        self.sync.recreate_connection()

        mock_fix_sp.assert_called_with(server_profile)
        mock_update.assert_called_with(
            '/rest/ethernet-networks/' + fake_network.oneview_network_id,
            server_profile,
            server_profile.get('connections')[0]
        )
        self.assertFalse(self.sync.neutron_client.port.create.called)

    @mock.patch.object(database_manager, 'get_port_with_binding_profile')
    @mock.patch.object(database_manager, 'list_neutron_oneview_network')
    @mock.patch.object(
        common, 'server_hardware_from_local_link_information_list')
    @mock.patch.object(common, 'local_link_information_from_port')
    @mock.patch.object(sync, '_update_connection')
    @mock.patch.object(sync, '_fix_connections_with_removed_networks')
    @mock.patch.object(common, 'get_database_session')
    def test_recreate_connection_no_nets(
            self, mock_session, mock_fix_sp, mock_update,
            mock_lli, mock_sh, mock_list_net, mock_port):
        session = mock_session()
        mock_port.return_value = [[
            {'network_id': '123',
             'mac_address': 'aa:11:cc:33:ee:44'},
            {'vnic_type': 'baremetal',
             'profile': '1111'}
        ]]
        port_dict = {
            'network_id': '123',
            'binding:vnic_type': 'baremetal',
            'binding:host_id': 'host_id',
            'mac_address': 'aa:11:cc:33:ee:44',
            'binding:profile': 1111
        }
        mock_list_net.return_value = []

        self.sync.recreate_connection()

        self.assertFalse(mock_fix_sp.called)
        self.assertFalse(mock_update.called)
        self.sync.neutron_client.port.create.assert_called_with(
            session, port_dict
        )
