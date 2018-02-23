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
from oslo_utils import importutils

from networking_oneview.conf import CONF
from networking_oneview.ml2.drivers.oneview import common
from networking_oneview.ml2.drivers.oneview import database_manager
from networking_oneview.ml2.drivers.oneview import exceptions
from networking_oneview.tests.unit.ml2.drivers.oneview\
    import test_oneview_mech_driver

CONF_UPLINKSET_MAPPINGS = (
    "physnet:lig_123:uplinkset_flat,physnet:lig_123:uplinkset_vlan")
CONF_FLAT_NET_MAPPINGS = "physnet-mapped:112233AA"

oneview_exceptions = importutils.try_import('hpOneView.exceptions')

DEFAULT_RETRY_INTERVAL = 0.001
DEFAULT_RETRY_LOCK = 4


class CommonTestCase(base.AgentMechanismBaseTestCase):
    def setUp(self):
        super(CommonTestCase, self).setUp()
        self.insecure = False
        self.ov_manager_url = "https://1.2.3.4"
        self.ov_username = "user"
        self.ov_password = "password"
        self.tls_cacert_file = "cacert_file"

        self.conf = CONF
        self.conf.oneview.allow_insecure_connections = self.insecure
        self.conf.oneview.oneview_host = self.ov_manager_url
        self.conf.oneview.username = self.ov_username
        self.conf.oneview.password = self.ov_password
        self.conf.oneview.tls_cacert_file = self.tls_cacert_file
        self.conf.DEFAULT.uplinkset_mappings = CONF_UPLINKSET_MAPPINGS
        self.conf.DEFAULT.flat_net_mappings = CONF_FLAT_NET_MAPPINGS
        self.conf.DEFAULT.retries_to_lock_sh_interval = DEFAULT_RETRY_INTERVAL
        self.conf.DEFAULT.retries_to_lock_sp_interval = DEFAULT_RETRY_INTERVAL

        self.credentials = {
            "ip": self.ov_manager_url,
            "credentials": {
                "userName": self.ov_username,
                "password": self.ov_password
            },
            "ssl_certificate": self.tls_cacert_file
        }

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    def test_get_oneview_client(self, mock_oneview_client):
        common.get_oneview_client()
        mock_oneview_client.assert_called_once_with(self.credentials)

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    def test_get_oneview_client_insecure_false(self, mock_oneview_client):
        self.conf.oneview.tls_cacert_file = None
        self.assertRaises(
            oneview_exceptions.HPOneViewException, common.get_oneview_client)

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    @mock.patch.object(database_manager, "get_neutron_oneview_network")
    def test_is_port_valid_to_reflect_on_oneview(
            self, mock_get_network, mock_oneview_client):
        local_link_information = (
            test_oneview_mech_driver.FAKE_PORT.get("binding:profile")
            .get("local_link_information"))
        self.assertTrue(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), test_oneview_mech_driver.FAKE_PORT,
                local_link_information))

    @mock.patch.object(common, "get_oneview_client")
    def test_is_port_valid_to_reflect_on_oneview_not_baremetal(
            self, mock_oneview_client):
        port = copy.deepcopy(test_oneview_mech_driver.FAKE_PORT)
        port["binding:vnic_type"] = "not_baremetal"
        lli = port.get("binding:profile").get("local_link_information")
        self.assertFalse(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), port, lli))

    @mock.patch.object(common, "get_oneview_client")
    @mock.patch.object(database_manager, "get_neutron_oneview_network")
    def test_is_port_valid_to_reflect_on_oneview_not_in_database(
            self, mock_get_network, mock_oneview_client):
        mock_get_network.return_value = None

        local_link_information = (
            test_oneview_mech_driver.FAKE_PORT.get("binding:profile")
            .get("local_link_information"))
        self.assertFalse(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), test_oneview_mech_driver.FAKE_PORT,
                local_link_information))

    @mock.patch.object(common, "get_oneview_client")
    @mock.patch.object(database_manager, "get_neutron_oneview_network")
    def test_is_port_valid_to_reflect_on_oneview_no_lli(
            self, mock_get_network, mock_oneview_client):
        lli = []
        self.assertFalse(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), test_oneview_mech_driver.FAKE_PORT, lli))

    @mock.patch.object(common, "get_oneview_client")
    @mock.patch.object(database_manager, "get_neutron_oneview_network")
    def test_is_port_valid_to_reflect_on_oneview_multiple_llis(
            self, mock_get_network, mock_oneview_client):
        lli = [{}, {}]
        self.assertFalse(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), test_oneview_mech_driver.FAKE_PORT, lli))

    @mock.patch.object(common, "get_oneview_client")
    @mock.patch.object(database_manager, "get_neutron_oneview_network")
    def test_is_port_valid_to_reflect_on_oneview_lli_no_switch_info(
            self, mock_get_network, mock_oneview_client):
        port = copy.deepcopy(test_oneview_mech_driver.FAKE_PORT)
        lli = port['binding:profile']['local_link_information']
        del lli[0]['switch_info']

        self.assertFalse(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), port, lli))

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    @mock.patch.object(database_manager, "get_neutron_oneview_network")
    def test_is_port_valid_to_reflect_on_oneview_lli_invalid_bootable(
            self, mock_get_network, mock_oneview_client):
        port = copy.deepcopy(test_oneview_mech_driver.FAKE_PORT)
        lli = port['binding:profile']['local_link_information']
        lli[0]['switch_info']['bootable'] = "invalid"

        self.assertFalse(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), port, lli))

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    @mock.patch.object(database_manager, "get_neutron_oneview_network")
    def test_is_port_valid_to_reflect_on_oneview_not_bootable(
            self, mock_get_network, mock_oneview_client):
        port = copy.deepcopy(test_oneview_mech_driver.FAKE_PORT)
        lli = port['binding:profile']['local_link_information']
        lli[0]['switch_info']['bootable'] = False

        self.assertTrue(
            common.is_port_valid_to_reflect_on_oneview(
                mock.MagicMock(), port, lli))

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    def test_get_oneview_client_insecure_cafile(self, mock_oneview_client):
        self.conf.oneview.allow_insecure_connections = True
        self.credentials["ssl_certificate"] = None
        common.get_oneview_client()
        mock_oneview_client.assert_called_once_with(self.credentials)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_flat_net_mappings_resources(self, mock_get_oneview_client):
        mock_oneview = mock_get_oneview_client()
        ethernet_networks = mock_oneview.ethernet_networks
        ethernet_networks.get.return_value = (
            test_oneview_mech_driver.FAKE_FLAT_ONEVIEW_NETWORK)
        ethernet_networks.get_associated_uplink_groups.return_value = (
            ['uplinkset/1'])

        common.check_flat_net_mappings_resources()

    @mock.patch.object(common, "get_oneview_client")
    def test_check_flat_net_mappings_resources_fail(
            self, mock_get_oneview_client):
        mock_oneview = mock_get_oneview_client()
        ethernet_networks = mock_oneview.ethernet_networks
        ethernet_networks.get.side_effect = (
            exceptions.OneViewResourceNotFoundException())

        self.assertRaises(exceptions.ClientException,
                          common.check_flat_net_mappings_resources)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_flat_net_mappings_resources_no_uplinkset(
            self, mock_get_oneview_client):
        mock_oneview = mock_get_oneview_client()
        ethernet_networks = mock_oneview.ethernet_networks
        ethernet_networks.get.return_value = (
            test_oneview_mech_driver.FAKE_FLAT_ONEVIEW_NETWORK)
        ethernet_networks.get_associated_uplink_groups.return_value = []

        self.assertRaises(exceptions.ClientException,
                          common.check_flat_net_mappings_resources)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_uplinkset_mappings_resources(self, mock_get_oneview_client):
        mock_oneview = mock_get_oneview_client()
        mock_oneview.logical_interconnect_groups.get.return_value = (
            test_oneview_mech_driver.FAKE_LIG)

        common.check_uplinkset_mappings_resources()

    @mock.patch.object(common, "get_oneview_client")
    def test_check_uplinkset_mappings_resources_fail(
            self, mock_get_oneview_client):
        self.conf.DEFAULT.uplinkset_mappings = 'does:not:exist,neither:do:I'
        mock_oneview = mock_get_oneview_client()
        mock_oneview.logical_interconnect_groups.get.return_value = (
            test_oneview_mech_driver.FAKE_LIG)

        self.assertRaises(exceptions.ClientException,
                          common.check_uplinkset_mappings_resources)

    def test_check_server_hardware_availability_locked(self):
        mock_sh = mock.MagicMock()
        mock_sh.get.return_value = "i'm busy"
        self.conf.DEFAULT.retries_to_lock_sh = DEFAULT_RETRY_LOCK
        self.assertFalse(
            common._check_server_hardware_availability(mock_sh))

        self.assertEqual(mock_sh.get.call_count, DEFAULT_RETRY_LOCK)

    def test_check_server_hardware_availability_unlocked_multiple_tries(self):
        power_lock_states = ["i'm busy", "i'm busy", None]
        mock_sh = mock.MagicMock()
        mock_sh.get.side_effect = power_lock_states
        self.conf.DEFAULT.retries_to_lock_sh = len(power_lock_states) + 1
        self.assertTrue(
            common._check_server_hardware_availability(mock_sh))

        self.assertEqual(mock_sh.get.call_count, len(power_lock_states))

    def test_check_server_hardware_availability_unlocked(self):
        mock_sh = mock.MagicMock()
        mock_sh.get.return_value = None
        self.conf.DEFAULT.retries_to_lock_sh = DEFAULT_RETRY_LOCK
        self.assertTrue(
            common._check_server_hardware_availability(mock_sh))

        self.assertEqual(mock_sh.get.call_count, 1)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_server_profile_availability_locked(
            self, mock_oneview_client):
        mock_oneview_client.get_server_profile_state.return_value = None
        self.conf.DEFAULT.retries_to_lock_sp = DEFAULT_RETRY_LOCK
        self.assertFalse(
            common._check_server_profile_availability(
                mock_oneview_client, mock.MagicMock()))

        self.assertEqual(
            mock_oneview_client.get_server_profile_state.call_count,
            DEFAULT_RETRY_LOCK)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_server_profile_availability_unlocked_multiple_tries(
            self, mock_oneview_client):
        server_profile_states = [None, None, "Normal"]
        mock_ov = mock_oneview_client
        mock_ov.get_server_profile_state.side_effect = server_profile_states
        self.conf.DEFAULT.retries_to_lock_sp = len(server_profile_states) + 1
        self.assertTrue(
            common._check_server_profile_availability(
                mock_oneview_client, mock.MagicMock()))
        self.assertEqual(mock_ov.get_server_profile_state.call_count,
                         len(server_profile_states))

    @mock.patch.object(common, "get_oneview_client")
    def test_check_server_profile_availability_unlocked(
            self, mock_oneview_client):
        mock_ov = mock_oneview_client
        mock_ov.get_server_profile_state.return_value = "Normal"
        self.conf.DEFAULT.retries_to_lock_sp = DEFAULT_RETRY_LOCK
        self.assertTrue(
            common._check_server_profile_availability(
                mock_oneview_client, mock.MagicMock()))
        self.assertEqual(mock_ov.get_server_profile_state.call_count, 1)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_unique_lig_per_provider_constraint(
            self, mock_oneview_client):
        success = True
        try:
            common.check_unique_lig_per_provider_constraint(
                test_oneview_mech_driver.UPLINKSET_MAPPINGS)
        except Exception:
            success = False

        self.assertTrue(success)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_unique_lig_per_provider_constraint_fails(
            self, mock_oneview_client):
        uplinkset_mappings_err = {
            'physnet': ['lig_123', 'uplinkset_flat'],
            'physnet2': ['lig_123', 'uplinkset_flat']
        }
        self.assertRaises(
            Exception, common.check_unique_lig_per_provider_constraint,
            uplinkset_mappings_err
        )

    @mock.patch.object(common, "get_oneview_client")
    def test_check_uplinkset_types_constraint(self, mock_oneview_client):
        success = True
        try:
            common.check_unique_lig_per_provider_constraint(
                test_oneview_mech_driver.UPLINKSET_MAPPINGS)
        except Exception:
            success = False

        self.assertTrue(success)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_uplinkset_types_constraint_fails(self, mock_oneview_client):
        client = mock_oneview_client()
        client.logical_interconnect_groups.get.return_value = (
            test_oneview_mech_driver.FAKE_LIG
        )
        uplinkset_mappings_err = {
            'physnet': ['lig_123', 'uplinkset_vlan',
                        'lig_123', 'uplinkset_vlan']
        }
        self.assertRaises(
            Exception, common.check_uplinkset_types_constraint,
            uplinkset_mappings_err
        )

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(common, 'get_database_session')
    def test_delete_outdated_flat_mapped_networks(
            self, mock_session, mock_delete, mock_oneview_client):
        common.delete_outdated_flat_mapped_networks(
            test_oneview_mech_driver.FLAT_NET_MAPPINGS)
        self.assertFalse(mock_delete.called)

    @mock.patch.object(common, 'OneViewClient', autospec=True)
    @mock.patch.object(database_manager, 'list_neutron_oneview_network')
    @mock.patch.object(database_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(common, 'get_database_session')
    def test_delete_outdated_flat_mapped_networks_clean(
            self, mock_session, mock_delete, mock_list_net,
            mock_oneview_client):
        network_unmapped = test_oneview_mech_driver.FakeNetwork()
        network_unmapped.manageable = False
        mock_list_net.return_value = [network_unmapped]
        common.delete_outdated_flat_mapped_networks(
            test_oneview_mech_driver.FLAT_NET_MAPPINGS)
        self.assertTrue(mock_delete.called)
