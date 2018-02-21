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
from oslo_utils import importutils

from networking_oneview.conf import CONF
from networking_oneview.ml2.drivers.oneview import common
from networking_oneview.ml2.drivers.oneview import exceptions
from networking_oneview.tests.unit.ml2.drivers.oneview\
    import test_oneview_mech_driver

CONF_UPLINKSET_MAPPINGS = (
    "physnet:lig_123:uplinkset_flat,physnet:lig_123:uplinkset_vlan")
CONF_FLAT_NET_MAPPINGS = "physnet-mapped:112233AA"

oneview_exceptions = importutils.try_import('hpOneView.exceptions')


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
    def test_check_flat_net_mappings_resources_fail(self,
            mock_get_oneview_client):
        mock_oneview = mock_get_oneview_client()
        ethernet_networks = mock_oneview.ethernet_networks
        ethernet_networks.get.side_effect = (
            exceptions.OneViewResourceNotFoundException())

        self.assertRaises(exceptions.ClientException,
            common.check_flat_net_mappings_resources)

    @mock.patch.object(common, "get_oneview_client")
    def test_check_flat_net_mappings_resources_no_uplinkset(self,
            mock_get_oneview_client):
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
    def test_check_uplinkset_mappings_resources_fail(self,
            mock_get_oneview_client):
        self.conf.DEFAULT.uplinkset_mappings = 'does:not:exist,neither:do:I'
        mock_oneview = mock_get_oneview_client()
        mock_oneview.logical_interconnect_groups.get.return_value = (
            test_oneview_mech_driver.FAKE_LIG)

        self.assertRaises(exceptions.ClientException,
            common.check_uplinkset_mappings_resources)
