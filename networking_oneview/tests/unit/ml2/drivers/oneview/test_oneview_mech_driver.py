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

import mock

from neutron.tests.unit.plugins.ml2 import _test_mech_agent as base

from networking_oneview.ml2.drivers.oneview import database_manager
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
FLAT_NET_MAPPINGS = {'physnet-mapped': ['ONEVIEW_NET1']}
FAKE_UPLINKSETS = [FAKE_TAGGED_UPLINKSET, FAKE_UNTAGGED_UPLINKSET]


class FakePlugin(object):
    def __init__(self):
        self._session = 'fake_session'


class FakeContext(object):
    def __init__(self):
        self._plugin_context = FakePlugin()
        self._network = None


class FakeNetwork(object):
    def __init__(self):
        self.oneview_network_id = '12345'
        self.manageable = True


class OneViewMechanismDriverTestCase(base.AgentMechanismBaseTestCase):
    def setUp(self):
        super(OneViewMechanismDriverTestCase, self).setUp()
        oneview_client = mock.MagicMock()
        oneview_client.logical_interconnect_groups.get.return_value = {
            'uplinkSets': FAKE_UPLINKSETS
        }
        database_manager.get_neutron_oneview_network = mock.Mock(
            return_value=False
        )
        self.driver = mech_oneview.OneViewDriver()
        self.driver.oneview_client = oneview_client
        self.driver.neutron_oneview_client = neutron_oneview_client.Client(
            oneview_client, UPLINKSET_MAPPINGS, FLAT_NET_MAPPINGS
        )

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
            ['ONEVIEW_NET1'], False, [])

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    def test_create_network_postcommit_flat(self, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_FLAT_NETWORK
        client = self.driver.oneview_client
        flat_network = {
            'name': 'Neutron [%s]' % FAKE_FLAT_NETWORK.get('id'),
            'ethernetNetworkType': 'Untagged',
            'vlanId': None,
            'purpose': 'General',
            'smartLink': False,
            'privateNetwork': False,
        }

        self.driver.create_network_postcommit(network_context)

        client.ethernet_networks.create.assert_called_with(flat_network)
        # NOTE(nicodemos) parameters: session, network_id, oneview_network_id,
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
        vlan_network = {
            'name': 'Neutron [%s]' % FAKE_VLAN_NETWORK.get('id'),
            'ethernetNetworkType': 'Tagged',
            'vlanId': '%s' % FAKE_VLAN_NETWORK.get('provider:segmentation_id'),
            'purpose': 'General',
            'smartLink': False,
            'privateNetwork': False,
        }

        self.driver.create_network_postcommit(network_context)

        client.ethernet_networks.create.assert_called_with(vlan_network)
        # NOTE(nicodemos) parameters: session, network_id, oneview_network_id,
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

    @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    @mock.patch.object(database_manager, 'get_neutron_oneview_network')
    def test_create_network_postcommit_net_created(
            self, mock_get_net, mock_map_net):
        network_context = FakeContext()
        network_context._network = FAKE_NETWORK_NOT_MAPPED
        client = self.driver.oneview_client
        mock_get_net.return_value = True

        self.driver.create_network_postcommit(network_context)

        self.assertFalse(client.ethernet_networks.create.called)
        self.assertFalse(mock_map_net.called)

    # NOTE(nicodemos): Waiting fix the bug when creating a unsupported
    # network type
    # @mock.patch.object(database_manager, 'map_neutron_network_to_oneview')
    # def test_create_network_postcommit_unsupported_type(self, mock_map_net):
    #     network_context = FakeContext()
    #     network_context._network = FAKE_VXLAN_NETWORK
    #     client = self.driver.oneview_client
    #
    #     self.driver.create_network_postcommit(network_context)
    #
    #     self.assertFalse(client.ethernet_networks.create.called)
    #     # NOTE(nicodemos) parameters: session, network_id,
    #     # oneview_network_id, manageable, mapping
    #     mock_map_net.assert_called_with()

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
