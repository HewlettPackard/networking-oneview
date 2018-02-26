# Copyright 2017 Hewlett Packard Enterprise Development LP.
# Copyright 2017 Universidade Federal de Campina Grande
# All Rights Reserved.
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

from neutron.tests.unit.plugins.ml2 import _test_mech_agent as base

from networking_oneview.ml2.drivers.oneview import common
from networking_oneview.ml2.drivers.oneview import database_manager
from networking_oneview.ml2.drivers.oneview import exceptions
from networking_oneview.ml2.drivers.oneview import mech_oneview
from networking_oneview.ml2.drivers.oneview import neutron_oneview_client

FAKE_FLAT_ONEVIEW_NETWORK = {
    'id': '1',
    'provider:physical_network': 'physnet-mapped',
    'provider:network_type': 'flat'
}
FAKE_FLAT_NETWORK = {
    'id': '2',
    'provider:physical_network': 'physnet',
    'provider:network_type': 'flat'
}
FAKE_VLAN_NETWORK = {
    'id': '3',
    'provider:segmentation_id': '123',
    'provider:physical_network': 'physnet',
    'provider:network_type': 'vlan'
}
FAKE_VXLAN_NETWORK = {
    'id': '3',
    'provider:segmentation_id': '123',
    'provider:physical_network': 'physnet',
    'provider:network_type': 'vxlan'
}
FAKE_NETWORK_NOT_MAPPED = {
    'id': '4',
    'provider:physical_network': 'not_mapped_phys',
    'provider:network_type': 'flat'
}
FAKE_NETWORK_SEGMENT = {
    'physical_network': 'physnet',
    'network_type': 'flat'
}
FAKE_NETWORK_SEGMENT_NOT_MAPPED = {
    'physical_network': 'not_mapped_phys',
    'network_type': 'flat'
}
FAKE_UNTAGGED_UPLINKSET = {
    'name': 'uplinkset_flat',
    'ethernetNetworkType': 'untagged',
    'networkUris': ['fake_net_uri']
}
FAKE_TAGGED_UPLINKSET = {
    'name': 'uplinkset_vlan',
    'ethernetNetworkType': 'tagged',
    'networkUris': ['fake_net_uri2']
}
UPLINKSET_MAPPINGS = {
    'physnet': ['lig_123', 'uplinkset_flat', 'lig_123', 'uplinkset_vlan']
}
FLAT_NET_MAPPINGS = {'physnet-mapped': ['112233AA']}
FAKE_LIG = {
    'uplinkSets': [FAKE_TAGGED_UPLINKSET, FAKE_UNTAGGED_UPLINKSET]
}

FAKE_PORT = {
    'id': '1',
    'mac_address': 'aa:11:cc:33:ee:44',
    'network_id': '1',
    'binding:vnic_type': 'baremetal',
    'binding:profile': {
        'local_link_information': [{
            "switch_info": {
                "server_hardware_id": "1122AA",
                "bootable": "true"
            },
            "port_id": "",
            "switch_id": "aa:bb:cc:dd:ee:ff"
        }]
    }
}

FAKE_SERVER_PROFILE = {
    'uri': '/fake_sp_uri',
    'status': 'ok',
    'connections': [{
        'portId': '1234',
        'networkUri': '/fake_net_uri',
        'mac': 'aa:11:cc:33:ee:44',
        'boot': {'priority': 'Primary'}
    }]
}
FAKE_SERVER_HARDWARE = {
    'uuid': '1122AA',
    'powerState': 'On',
    'serverProfileUri': '/fake_sp_uri',
    'locationUri': '/fake_enclosure_uri',
    'powerLock': False,
    'portMap': {
        'deviceSlots': [{
            'slotNumber': '1',
            'location': 'Flb',
            'physicalPorts': [{
                'portNumber': '1',
                'virtualPorts': [{
                    'mac': 'aa:11:cc:33:ee:44',
                    'portFunction': 'a',
                }]
            }]
        }]
    }
}

FAKE_OV_FLAT_NETWORK = {
    'name': 'Neutron [%s]' % FAKE_FLAT_NETWORK.get('id'),
    'ethernetNetworkType': 'Untagged',
    'vlanId': None,
    'purpose': 'General',
    'smartLink': False,
    'privateNetwork': False,
}

FAKE_OV_VLAN_NETWORK = {
    'name': 'Neutron [%s]' % FAKE_VLAN_NETWORK.get('id'),
    'ethernetNetworkType': 'Tagged',
    'vlanId': '%s' % FAKE_VLAN_NETWORK.get('provider:segmentation_id'),
    'purpose': 'General',
    'smartLink': False,
    'privateNetwork': False,
}


class FakeContext(object):
    def __init__(self):
        self._plugin_context = FakePlugin()
        self._network = None
        self._port = copy.deepcopy(FAKE_PORT)
        self.current = copy.deepcopy(FAKE_PORT)
        self.segments_to_bind = []


class FakePlugin(object):
    def __init__(self):
        self._session = 'fake_session'


class FakeNetwork(object):
    def __init__(self):
        self.oneview_network_id = '12345'
        self.neutron_network_id = '54321'
        self.manageable = True


class OneViewMechanismDriverTestCase(base.AgentMechanismBaseTestCase):
    def setUp(self):
        super(OneViewMechanismDriverTestCase, self).setUp()
        common.get_oneview_client = mock.MagicMock()
        oneview_client = common.get_oneview_client()
        oneview_client.logical_interconnect_groups.get.return_value = FAKE_LIG
        database_manager.get_neutron_oneview_network = mock.Mock(
            return_value=False
        )
        self.driver = mech_oneview.OneViewDriver()
        self.driver.oneview_client = oneview_client
        self.driver.neutron_oneview_client = neutron_oneview_client.Client(
            oneview_client, UPLINKSET_MAPPINGS, FLAT_NET_MAPPINGS
        )
        self.server_hardware = copy.deepcopy(FAKE_SERVER_HARDWARE)
        self.server_profile = copy.deepcopy(FAKE_SERVER_PROFILE)

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_network_postcommit_flat_mapping(self, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_ONEVIEW_NETWORK
        client = self.driver.oneview_client

        self.driver.create_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.create.called)
        # NOTE(nicodemos) parameters: session, network_id, oneview_network_id,
        # manageable, mapping
        mock_map_net.assert_called_with(
            network_context._plugin_context._session,
            FAKE_FLAT_ONEVIEW_NETWORK.get('id'),
            ['112233AA'], False, [])

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_network_postcommit_flat(self, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_NETWORK
        client = self.driver.oneview_client

        client.ethernet_networks.get_by.return_value = []
        self.driver.create_network_postcommit(network_context)

        client.ethernet_networks.create.assert_called_with(
            FAKE_OV_FLAT_NETWORK
        )
        # NOTE(nicodemos) parameters: session, network_id, oneview_network_id,
        # manageable, mapping
        mock_map_net.assert_called_with(
            network_context._plugin_context._session,
            FAKE_FLAT_NETWORK.get('id'),
            mock.ANY, True, ['lig_123', 'uplinkset_flat'])

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_already_existing_network_postcommit_flat(
        self, mock_map_net
    ):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_NETWORK
        client = self.driver.oneview_client

        client.ethernet_networks.get_by.return_value = [FAKE_OV_FLAT_NETWORK]
        self.driver.create_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.create.called)
        # NOTE(gustavo) parameters: session, network_id, oneview_network_id,
        # manageable, mapping
        mock_map_net.assert_called_with(
            network_context._plugin_context._session,
            FAKE_FLAT_NETWORK.get('id'),
            mock.ANY, True, ['lig_123', 'uplinkset_flat'])

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_network_postcommit_vlan(self, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_VLAN_NETWORK
        client = self.driver.oneview_client
        client.ethernet_networks.get_by.return_value = []

        self.driver.create_network_postcommit(network_context)
        client.ethernet_networks.create.assert_called_with(
            FAKE_OV_VLAN_NETWORK
        )
        # NOTE(nicodemos) parameters: session, network_id, oneview_network_id,
        # manageable, mapping
        mock_map_net.assert_called_with(
            network_context._plugin_context._session,
            FAKE_VLAN_NETWORK.get('id'),
            mock.ANY, True, ['lig_123', 'uplinkset_vlan'])

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_already_existing_network_postcommit_vlan(
        self, mock_map_net
    ):
        network_context = FakeContext()
        network_context._network = FAKE_VLAN_NETWORK
        client = self.driver.oneview_client
        client.ethernet_networks.get_by.return_value = [FAKE_OV_VLAN_NETWORK]

        self.driver.create_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.create.called)
        # NOTE(gustavo) parameters: session, network_id, oneview_network_id,
        # manageable, mapping
        mock_map_net.assert_called_with(
            network_context._plugin_context._session,
            FAKE_VLAN_NETWORK.get('id'),
            mock.ANY, True, ['lig_123', 'uplinkset_vlan'])

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_network_postcommit_not_mapped(self, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_NETWORK_NOT_MAPPED
        client = self.driver.oneview_client

        self.driver.create_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.create.called)
        self.assertFalse(mock_map_net.called)

    @mock.patch.object(neutron_oneview_client.Network, '_add_to_ligs')
    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_network_postcommit_in_lig(self, mock_map_net, mock_add):
        network_context = FakeContext()
        network_context._network = FAKE_VLAN_NETWORK
        client = self.driver.oneview_client
        mock_add.side_effect = Exception("BOOM")

        vlan_network = {
            'name': 'Neutron [%s]' % FAKE_VLAN_NETWORK.get('id'),
            'ethernetNetworkType': 'Tagged',
            'vlanId': '%s' % FAKE_VLAN_NETWORK.get('provider:segmentation_id'),
            'purpose': 'General',
            'smartLink': False,
            'privateNetwork': False,
        }

        self.assertRaises(
            exceptions.NetworkCreationException,
            self.driver.create_network_postcommit,
            network_context
        )
        client.ethernet_networks.create.assert_called_with(vlan_network)
        self.assertTrue(client.ethernet_networks.delete.called)
        self.assertFalse(mock_map_net.called)

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    def test_create_network_postcommit_net_created(
            self, mock_get_net, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_NETWORK
        client = self.driver.oneview_client
        mock_get_net.return_value = True

        self.driver.create_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.create.called)
        self.assertFalse(mock_map_net.called)

    # NOTE(nicodemos): See bug when creating a unsupported network type
    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_network_postcommit_unsupported_type(self, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_VXLAN_NETWORK
        client = self.driver.oneview_client

        self.driver.create_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.create.called)
        self.assertFalse(mock_map_net.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_oneview_network_lig')
    def test_delete_network_postcommit(self, mock_del_lig,
                                       mock_del_net, mock_get_net):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_NETWORK
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client

        self.driver.delete_network_postcommit(network_context)

        client.ethernet_networks.delete.assert_called_with(
            fake_network_obj.oneview_network_id)
        mock_del_net.assert_called_with(
            network_context._plugin_context._session,
            neutron_network_id=FAKE_FLAT_NETWORK.get('id')
        )
        mock_del_lig.assert_called_with(
            network_context._plugin_context._session,
            oneview_network_id=fake_network_obj.oneview_network_id
        )

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_oneview_network_lig')
    def test_delete_network_postcommit_flat_mapping(
            self, mock_del_lig, mock_del_net, mock_get_net):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_ONEVIEW_NETWORK
        fake_network_obj = FakeNetwork()
        fake_network_obj.manageable = False
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client

        self.driver.delete_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.delete.called)
        mock_del_net.assert_called_with(
            network_context._plugin_context._session,
            neutron_network_id=FAKE_FLAT_ONEVIEW_NETWORK.get('id')
        )
        mock_del_lig.assert_called_with(
            network_context._plugin_context._session,
            oneview_network_id=fake_network_obj.oneview_network_id
        )

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_oneview_network_lig')
    def test_delete_network_postcommit_no_network(
            self, mock_del_lig, mock_del_net, mock_get_net):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_ONEVIEW_NETWORK
        mock_get_net.return_value = None
        client = self.driver.oneview_client

        self.driver.delete_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.delete.called)
        self.assertFalse(mock_del_net.called)
        self.assertFalse(mock_del_lig.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        client.server_hardware.get.return_value = self.server_hardware
        client.server_profiles.get.return_value = self.server_profile

        old_connections = copy.deepcopy(self.server_profile['connections'])
        self.driver.bind_port(port_context)
        new_connections = self.server_profile['connections']

        self.assertNotEqual(old_connections, new_connections)
        client.server_profiles.update.assert_called_with(
            id_or_uri=self.server_profile.get('uri'),
            resource={
                'uri': self.server_profile.get('uri'),
                'status': self.server_profile.get('status'),
                'connections': self.server_profile['connections']
            })

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_existing_conn(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        client.server_hardware.get.return_value = self.server_hardware
        client.server_profiles.get.return_value = self.server_profile

        self.server_profile["connections"][0]["portId"] = "Flb 1:1-a"
        old_connections = copy.deepcopy(self.server_profile['connections'])
        self.driver.bind_port(port_context)
        new_connections = self.server_profile['connections']

        for old_conn in old_connections:
            for new_conn in new_connections:
                if old_conn.get('mac') == new_conn.get('mac'):
                    self.assertEqual(old_conn.get('portId'),
                                     new_conn.get('portId'))
                    self.assertNotEqual(old_conn.get('networkUri'),
                                        new_conn.get('networkUri'))
                    self.assertEqual(old_conn.get('boot'),
                                     new_conn.get('boot'))

        self.assertEqual(len(old_connections), len(new_connections))
        client.server_profiles.update.assert_called_with(
            id_or_uri=self.server_profile.get('uri'),
            resource={
                'uri': self.server_profile.get('uri'),
                'status': self.server_profile.get('status'),
                'connections': self.server_profile['connections']
            })

    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_net_not_mapped(self, mock_net_segment):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT_NOT_MAPPED
        client = self.driver.oneview_client

        self.driver.bind_port(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_not_baremetal(self, mock_net_segment):
        port_context = FakeContext()
        port_context._port['binding:vnic_type'] = 'not_baremetal'
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        client = self.driver.oneview_client

        self.driver.bind_port(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_not_in_database(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        mock_get_net.return_value = None
        client = self.driver.oneview_client

        self.driver.bind_port(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_no_link_info(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        port_context._port['binding:profile']['local_link_information'] = None
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client

        self.driver.bind_port(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_more_link_info(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        port_context._port['binding:profile']['local_link_information'].append(
            {'fake_local_link_info': True}
        )
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client

        self.driver.bind_port(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_no_switch_info(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        port_context._port[
            'binding:profile']['local_link_information'][0][
                'switch_info'] = None
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client

        self.driver.bind_port(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_not_bootable(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        switch_info = port_context._port[
            'binding:profile']['local_link_information'][0]['switch_info']
        switch_info['bootable'] = False
        port_context._port[
            'binding:profile']['local_link_information'][0][
                'switch_info'] = switch_info
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        client.server_hardware.get.return_value = self.server_hardware
        client.server_profiles.get.return_value = self.server_profile

        old_connections = copy.deepcopy(self.server_profile['connections'])
        self.driver.bind_port(port_context)
        new_connections = self.server_profile['connections']
        boot_info = new_connections[1].get('boot').get('priority')

        self.assertNotEqual(old_connections, new_connections)
        self.assertTrue(client.server_hardware.get.called)
        self.assertTrue(client.server_profiles.get.called)
        self.assertEqual(boot_info, 'NotBootable')
        client.server_profiles.update.assert_called_with(
            id_or_uri=self.server_profile.get('uri'),
            resource={
                'uri': self.server_profile.get('uri'),
                'status': self.server_profile.get('status'),
                'connections': self.server_profile['connections']
            })

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_no_hardware(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        switch_info = port_context._port[
            'binding:profile']['local_link_information'][0]['switch_info']
        switch_info['server_hardware_id'] = None
        port_context._port[
            'binding:profile']['local_link_information'][0][
                'switch_info'] = switch_info
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client

        self.driver.bind_port(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_no_profile(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        self.server_hardware['serverProfileUri'] = None
        client.server_hardware.get.return_value = self.server_hardware

        self.driver.bind_port(port_context)

        self.assertTrue(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_rack_server(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        self.server_hardware['locationUri'] = None
        client.server_hardware.get.return_value = self.server_hardware

        self.driver.bind_port(port_context)

        self.assertTrue(client.server_hardware.get.called)
        self.assertTrue(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_create_port_no_pxe_bootable_available(
            self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        client.server_hardware.get.return_value = self.server_hardware
        client.server_profiles.get.return_value = self.server_profile
        new_connection = {
            'portId': '231',
            'networkUri': '/fake_net_uri_2',
            'mac': 'aa:11:22:33:ee:44',
            'boot': {'priority': 'Secondary'}
        }
        self.server_profile['connections'].append(new_connection)

        self.driver.bind_port(port_context)

        self.assertTrue(client.server_hardware.get.called)
        self.assertTrue(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_delete_port_postcommit(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        client.server_hardware.get.return_value = self.server_hardware
        client.server_profiles.get.return_value = self.server_profile

        self.driver.delete_port_postcommit(port_context)

        client.server_profiles.update.assert_called_with(
            id_or_uri=self.server_profile.get('uri'),
            resource={
                'uri': self.server_profile.get('uri'),
                'status': self.server_profile.get('status'),
                'connections': self.server_profile['connections']
            })

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_delete_port_postcommit_not_valid(
            self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        port_context._port['binding:profile']['local_link_information'] = None
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client

        self.driver.delete_port_postcommit(port_context)

        self.assertFalse(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)

    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    @mock.patch.object(database_manager, 'get_network_segment')
    def test_delete_port_rack_server(self, mock_net_segment, mock_get_net):
        port_context = FakeContext()
        mock_net_segment.return_value = FAKE_NETWORK_SEGMENT
        fake_network_obj = FakeNetwork()
        mock_get_net.return_value = fake_network_obj
        client = self.driver.oneview_client
        self.server_hardware['locationUri'] = None
        client.server_hardware.get.return_value = self.server_hardware

        self.driver.delete_port_postcommit(port_context)

        self.assertTrue(client.server_hardware.get.called)
        self.assertFalse(client.server_profiles.get.called)
        self.assertFalse(client.server_profiles.update.called)
