#
# Copyright 2016 Hewlett Packard Development Company, LP
# Copyright 2016 Universidade Federal de Campina Grande
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

from neutron.db import models_v2
from neutron.db import oneview_network_db
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from neutron.plugins.ml2.drivers.oneview import mech_oneview
from neutron.tests.unit.plugins.ml2 import _test_mech_agent as base
from oneview_client import client
from oneview_client import exceptions
from oneview_client import managers
from oneview_client import models
from oslo_config import cfg
from sqlalchemy.orm.session import Session


NETWORK_TYPE_TAG = 'Tagged'
NETWORK_TYPE_VXLAN = 'vxlan'
NETWORK_TYPE_VLAN = 'vlan'

NETWORK_ID = 'net-id'

NETWORK_SEGMENTATION_ID = 'provider:segmentation_id'
NETWORK_NETWORK_TYPE = 'provider:network_type'
NETWORK_NAME = 'name'

PORT_ID = 'p-id'
VNIC_TYPE_BAREMETAL = 'baremetal'
MAC_ONE = 'aa:bb:cc:dd:ee:ff'
MAC_TWO = 'aa:bb:cc:dd:ee:gg'
SERVER_HARDWARE_UUID = 'sh-uuid'
BOOT_PRIMARY = 'primary'


class FakePluginContext(object):
    """Context for testing purposes only"""
    def __init__(self):
        self._session = Session()


class FakeNetworkContext(api.NetworkContext):
    """Network context for testing purposes only."""
    def __init__(self, network, original_network=None):
        self._network = network
        self._original_network = original_network
        self._plugin_context = FakePluginContext()

    @property
    def current(self):
        return {'id': self._network.get('id')}

    @property
    def original(self):
        return None

    @property
    def network_segments(self):
        return None


class FakePortContext(object):
    """Network context for testing purposes only."""
    def __init__(self, port, original_port, network_context):
        self._plugin_context = FakePluginContext()
        self._port = port
        self._original_port = original_port
        self._network_context = network_context

    @property
    def current(self):
        return self._port

    @property
    def original(self):
        return self._original_port

    @property
    def network(self):
        return self._network_context

    @property
    def host(self):
        return None

    @property
    def original_host(self):
        return None

    @property
    def status(self):
        return 'ACTIVE'


def _create_network_context(name, network_type, vlan_id=0, network_id=1):
    network = {
        NETWORK_NAME: name,
        NETWORK_NETWORK_TYPE: network_type,
        'id': network_id
    }
    if network_type == NETWORK_TYPE_VXLAN or network_type == NETWORK_TYPE_VLAN:
        network[NETWORK_SEGMENTATION_ID] = vlan_id

    network_context = FakeNetworkContext(network)
    return network_context


def _create_port_context_body(mac, port_id, vnic_type):
    body = {
        'mac_address': mac,
        'id': PORT_ID,
        'binding:vnic_type': vnic_type,
    }

    return body


def _create_port_context_body_with_binding_profile(
    mac, port_id, vnic_type, server_hardware_uuid, boot_priority
):
    binding_profile = {
        'local_link_information': [{
            'switch_info': {
                'server_hardware_uuid': server_hardware_uuid,
                'boot_priority': boot_priority
            }
        }]
    }
    body = _create_port_context_body(mac, port_id, vnic_type)
    body['binding:profile'] = binding_profile

    return body


def _create_port_context_without_local_link_information(
    mac, vnic_type=VNIC_TYPE_BAREMETAL
):
    port = _create_port_context_body(mac, PORT_ID, vnic_type)
    network_context = _create_network_context('net', NETWORK_TYPE_VLAN)

    context = FakePortContext(port, port, network_context)
    return context


def _create_port_context(
    boot_priority, mac, server_hardware_uuid=SERVER_HARDWARE_UUID,
    vnic_type=VNIC_TYPE_BAREMETAL
):
    context = _create_port_context_without_local_link_information(
        mac, vnic_type
    )
    port = context._port
    port['binding:profile'] = {
        'local_link_information': [{
            'switch_info': {
                'server_hardware_uuid': server_hardware_uuid,
                'boot_priority': boot_priority
            }
        }]
    }

    context._original_port = port
    return context


def _create_port_context_with_update(
    boot_priority, new_boot_priority, mac, new_mac,
    server_hardware_uuid=SERVER_HARDWARE_UUID, vnic_type=VNIC_TYPE_BAREMETAL
):
    original_port = _create_port_context_body_with_binding_profile(
        mac, PORT_ID, vnic_type, server_hardware_uuid, boot_priority
    )
    port = _create_port_context_body_with_binding_profile(
        new_mac, PORT_ID, vnic_type, server_hardware_uuid, new_boot_priority
    )

    network_context = _create_network_context('net', NETWORK_TYPE_VLAN)

    context = FakePortContext(port, original_port, network_context)

    return context


class OneViewMechanismDriverTestCase(base.AgentMechanismBaseTestCase):
    @mock.patch.object(client.BaseClient, 'get_session', autospec=True)
    def setUp(self, mock_get_session):
        super(OneViewMechanismDriverTestCase, self).setUp()
        cfg.CONF.set_override(
            'manager_url', 'https://1.2.3.4', group='oneview'
        )
        cfg.CONF.set_override('username', 'user', group='oneview')
        cfg.CONF.set_override('password', 'password', group='oneview')
        cfg.CONF.set_override(
            'allow_insecure_connections', True, group='oneview'
        )
        cfg.CONF.set_override('tls_cacert_file', None, group='oneview')
        cfg.CONF.set_override('max_polling_attempts', 12, group='oneview')
        cfg.CONF.set_override('uplinksets_uuid', 'us-uuid', group='oneview')
        self.driver = mech_oneview.OneViewDriver()
        self.driver.initialize()

    @mock.patch.object(managers.UplinkSetManager, 'add_network', autospec=True)
    def test__add_network_to_one_uplink_set(
        self, mock_add_network
    ):
        uplinkset_uuid = 'uuid'
        uplinksets_uuid = [uplinkset_uuid]
        oneview_network_uuid = 'net-uuid'

        self.driver._add_network_to_uplinksets(
            uplinksets_uuid, oneview_network_uuid
        )

        mock_add_network.assert_called_once_with(
            self.driver.oneview_client.uplink_set, uplinkset_uuid,
            oneview_network_uuid
        )

    @mock.patch.object(managers.UplinkSetManager, 'add_network', autospec=True)
    def test__add_network_to_multiple_uplink_sets(
         self, mock_add_network
    ):
        uplinkset_uuid_one = 'uuid-1'
        uplinkset_uuid_two = 'uuid-2'
        uplinksets_uuid = [uplinkset_uuid_one, uplinkset_uuid_two]
        oneview_network_uuid = 'net-uuid'

        self.driver._add_network_to_uplinksets(
            uplinksets_uuid, oneview_network_uuid
        )

        calls = [
            mock.call(
                self.driver.oneview_client.uplink_set,
                uplinkset_uuid_one, oneview_network_uuid
            ),
            mock.call(
                self.driver.oneview_client.uplink_set,
                uplinkset_uuid_two, oneview_network_uuid
            ),
        ]
        mock_add_network.assert_has_calls(calls, any_order=True)

    @mock.patch.object(
        managers.EthernetNetworkManager, 'create', autospec=True
    )
    @mock.patch.object(
        mech_oneview.OneViewDriver, '_add_network_to_uplinksets', autospec=True
    )
    @mock.patch.object(
        db_manager, 'insert_neutron_oneview_network', autospec=True
    )
    @mock.patch.object(
        db_manager, 'insert_oneview_network_uplinkset', autospec=True
    )
    def test_create_network_postcommit_with_vxlan_and_one_uplinkset(
        self, mock_insert_oneview_network_uplinkset,
        mock_insert_neutron_oneview_network,
        mock__add_network_to_uplinksets, mock_create
    ):
        oneview_network_uuid = 'net-uuid'
        oneview_network_uri = '/rest/ethernet-networks/' + oneview_network_uuid
        network_name = 'test-network'
        vlan_id = '100'
        neutron_network_id = 1
        uplinkset_uuid = 'us-uuid'
        cfg.CONF.set_override(
            'uplinksets_uuid', uplinkset_uuid, group='oneview'
        )

        network_context = _create_network_context(
            network_name, NETWORK_TYPE_VXLAN, vlan_id, neutron_network_id
        )

        mock_create.return_value = oneview_network_uri

        self.driver.create_network_postcommit(network_context)

        mock_create.assert_called_once_with(
            self.driver.oneview_client.ethernet_network,
            name=network_name,
            ethernet_network_type=NETWORK_TYPE_TAG,
            vlan=vlan_id
        )

        uplinksets_uuid = cfg.CONF.oneview.uplinksets_uuid.split(",")
        mock__add_network_to_uplinksets.assert_called_once_with(
            self.driver, [uplinkset_uuid], oneview_network_uuid
        )
        mock_insert_neutron_oneview_network.assert_called_once_with(
            network_context._plugin_context._session, neutron_network_id,
            oneview_network_uuid
        )
        mock_insert_oneview_network_uplinkset.assert_called_once_with(
            network_context._plugin_context._session, oneview_network_uuid,
            uplinkset_uuid
        )

    @mock.patch.object(
        managers.EthernetNetworkManager, 'create', autospec=True
    )
    @mock.patch.object(
        mech_oneview.OneViewDriver, '_add_network_to_uplinksets', autospec=True
    )
    @mock.patch.object(
        db_manager, 'insert_neutron_oneview_network', autospec=True
    )
    @mock.patch.object(
        db_manager, 'insert_oneview_network_uplinkset', autospec=True
    )
    def test_create_network_postcommit_with_vxlan_and_many_uplinkset(
        self, mock_insert_oneview_network_uplinkset,
        mock_insert_neutron_oneview_network,
        mock__add_network_to_uplinksets, mock_create
    ):
        oneview_network_uuid = 'net-uuid'
        oneview_network_uri = '/rest/ethernet-networks/' + oneview_network_uuid
        network_name = 'test-network'
        vlan_id = '100'
        neutron_network_id = 1
        uplinkset_uuid_one = 'us-uuid-1'
        uplinkset_uuid_two = 'us-uuid-2'
        cfg.CONF.set_override(
            'uplinksets_uuid', uplinkset_uuid_one + "," + uplinkset_uuid_two,
            group='oneview'
        )

        network_context = _create_network_context(
            network_name, NETWORK_TYPE_VXLAN, vlan_id, neutron_network_id
        )

        mock_create.return_value = oneview_network_uri

        self.driver.create_network_postcommit(network_context)

        mock_create.assert_called_once_with(
            self.driver.oneview_client.ethernet_network,
            name=network_name,
            ethernet_network_type=NETWORK_TYPE_TAG,
            vlan=vlan_id
        )

        uplinksets_uuid = cfg.CONF.oneview.uplinksets_uuid.split(",")
        mock__add_network_to_uplinksets.assert_called_once_with(
            self.driver, [uplinkset_uuid_one, uplinkset_uuid_two],
            oneview_network_uuid
        )
        mock_insert_neutron_oneview_network.assert_called_once_with(
            network_context._plugin_context._session, neutron_network_id,
            oneview_network_uuid
        )

        calls = [
            mock.call(
                network_context._plugin_context._session,
                oneview_network_uuid, uplinkset_uuid_one
            ),
            mock.call(
                network_context._plugin_context._session,
                oneview_network_uuid, uplinkset_uuid_two
            )
        ]

        mock_insert_oneview_network_uplinkset.assert_has_calls(
            calls, any_order=True
        )

    @mock.patch.object(
        db_manager, 'get_neutron_oneview_network', autospec=True
    )
    @mock.patch.object(
        managers.EthernetNetworkManager, 'delete', autospec=True
    )
    @mock.patch.object(
        db_manager, 'delete_neutron_oneview_network', autospec=True
    )
    @mock.patch.object(
        db_manager, 'delete_oneview_network_uplinkset', autospec=True
    )
    def test_delete_network_postcommit(
        self, mock_delete_oneview_network_uplinkset,
        mock_delete_neutron_oneview_network, mock_delete,
        mock_get_neutron_oneview_network
    ):
        oneview_network_uuid = 'oneview_net_uuid'
        network_name = 'net-name'
        neutron_network_id = 1
        network_context = _create_network_context(
            network_name, NETWORK_TYPE_VXLAN,
            network_id=neutron_network_id
        )
        session = network_context._plugin_context._session

        neutron_oneview_network = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_id, oneview_network_uuid
        )

        mock_get_neutron_oneview_network.return_value =\
            neutron_oneview_network

        self.driver.delete_network_postcommit(network_context)

        mock_delete.assert_called_once_with(
            self.driver.oneview_client.ethernet_network,
            oneview_network_uuid
        )

        mock_delete_neutron_oneview_network.assert_called_once_with(
            session, neutron_network_id
        )
        mock_delete_oneview_network_uplinkset.assert_called_once_with(
            session, oneview_network_uuid
        )

    @mock.patch.object(
        managers.EthernetNetworkManager, 'get', autospec=True
    )
    @mock.patch.object(
        db_manager, 'get_neutron_oneview_network', autospec=True
    )
    def test_update_network_postcommit(
        self, mock_get_neutron_oneview_network, mock_get
    ):
        oneview_network_uuid = 'net-uuid'
        oneview_network_uri = '/rest/ethernet-networks/' + oneview_network_uuid
        network_name = 'test-network'
        vlan_id = '100'
        neutron_network_id = 1

        network_context = _create_network_context(
            network_name, NETWORK_TYPE_VXLAN, vlan_id, neutron_network_id
        )

        neutron_oneview_network = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_id, oneview_network_uuid
        )

        mock_get_neutron_oneview_network.return_value = neutron_oneview_network

        self.driver.update_network_postcommit(network_context)

        mock_get_neutron_oneview_network.assert_called_once_with(
            network_context._plugin_context._session, neutron_network_id
        )

        mock_get.assert_called_once_with(
            self.driver.oneview_client.ethernet_network,
            neutron_oneview_network.oneview_network_uuid
        )

    def test_create_port_postcommit_not_baremetal_type(self):
        context = _create_port_context_without_local_link_information(
            MAC_ONE, vnic_type='not baremetal'
        )
        self.driver.create_port_postcommit(context)

    def test_create_port_postcommit_without_local_link_information(self):
        context = _create_port_context_without_local_link_information(
            MAC_ONE, vnic_type='not baremetal'
        )
        self.driver.create_port_postcommit(context)

    @mock.patch.object(
        managers.ServerHardwareManager, 'get', spec_set=True, autospec=True
    )
    @mock.patch.object(
        db_manager, 'get_neutron_oneview_network', spec_set=True, autospec=True
    )
    @mock.patch.object(
        models.ServerHardware, 'generate_connection_port_for_mac',
        spec_set=True, autospec=True
    )
    @mock.patch.object(
        managers.ServerProfileManager, 'add_connection', spec_set=True,
        autospec=True
    )
    @mock.patch.object(
        db_manager, 'insert_neutron_oneview_port', spec_set=True, autospec=True
    )
    def test_create_port_postcommit(
        self, mock_insert_neutron_oneview_port, mock_add_connection,
        mock_generate_connection_port_for_mac,
        mock_get_neutron_oneview_network, mock_sh_get
    ):
        server_profile_uuid = 'sp-uuid'
        server_profile_uri = '/rest/server-profile/' + server_profile_uuid
        oneview_network_uuid = 'ov-net-uuid'
        context = _create_port_context(
            boot_priority=BOOT_PRIMARY,
            mac=MAC_ONE,
            server_hardware_uuid=SERVER_HARDWARE_UUID,
            vnic_type=VNIC_TYPE_BAREMETAL
        )

        server_hardware = models.ServerHardware()
        server_hardware.server_profile_uri = server_profile_uri

        neutron_oneview_network = oneview_network_db.NeutronOneviewNetwork(
            'neutron_network_uuid',
            oneview_network_uuid
        )
        conn_id = '1'
        connection = {'id': conn_id}

        mock_sh_get.return_value = server_hardware
        mock_get_neutron_oneview_network.return_value = neutron_oneview_network
        mock_generate_connection_port_for_mac.return_value = 'port'
        mock_add_connection.return_value = connection

        self.driver.create_port_postcommit(context)

        mock_sh_get.assert_called_once_with(
            self.driver.oneview_client.server_hardware, SERVER_HARDWARE_UUID
        )
        mock_get_neutron_oneview_network.assert_called_once_with(
            context._plugin_context._session,
            context._network_context._network.get('id')
        )

        mock_add_connection.assert_called_once_with(
            self.driver.oneview_client.server_profile, server_profile_uuid,
            oneview_network_uuid, BOOT_PRIMARY, 'port'
        )

        mock_insert_neutron_oneview_port.assert_called_once_with(
            context._plugin_context._session, PORT_ID, server_profile_uuid,
            conn_id
        )

    @mock.patch.object(
        db_manager, 'get_neutron_oneview_port', spec_set=True, autospec=True
    )
    @mock.patch.object(
        managers.ServerProfileManager, 'remove_connection', spec_set=True,
        autospec=True
    )
    @mock.patch.object(
        db_manager, 'delete_neutron_oneview_port', spec_set=True, autospec=True
    )
    def test_delete_port_postcommit(
        self, mock_delete_neutron_oneview_port, mock_remove_connection,
        mock_get_neutron_oneview_port
    ):
        server_profile_uuid = 'sp-uuid'
        conn_id = 1
        context = _create_port_context(
            boot_priority=BOOT_PRIMARY,
            mac=MAC_ONE,
            server_hardware_uuid=SERVER_HARDWARE_UUID,
            vnic_type=VNIC_TYPE_BAREMETAL
        )
        session = context._plugin_context._session

        neutron_oneview_port = oneview_network_db.NeutronOneviewPort(
            PORT_ID, server_profile_uuid, conn_id
        )
        mock_get_neutron_oneview_port.return_value = neutron_oneview_port

        self.driver.delete_port_postcommit(context)

        mock_get_neutron_oneview_port.assert_called_once_with(
            session, PORT_ID
        )

        mock_remove_connection.assert_called_once_with(
            self.driver.oneview_client.server_profile, server_profile_uuid,
            conn_id
        )

        mock_delete_neutron_oneview_port.assert_called_once_with(
            session, PORT_ID
        )

    @mock.patch.object(
        db_manager, 'get_neutron_oneview_port', spec_set=True, autospec=True
    )
    @mock.patch.object(
        managers.ServerHardwareManager, 'get', spec_set=True, autospec=True
    )
    @mock.patch.object(
        managers.ServerProfileManager, 'update_connection', spec_set=True,
        autospec=True
    )
    @mock.patch.object(
        models.ServerHardware, 'generate_connection_port_for_mac',
        spec_set=True, autospec=True
    )
    def test_update_port_postcommit_update_mac(
        self, mock_generate_connection_port_for_mac, mock_update_connection,
        mock_sh_get, mock_get_neutron_oneview_port
    ):
        server_profile_uuid = 'sp-uuid'
        server_profile_uri = '/rest/server-profile/' + server_profile_uuid
        conn_id = 1
        new_boot_priority = 'not_bootable'
        context = _create_port_context_with_update(
            'primary', new_boot_priority, MAC_ONE, MAC_TWO,
            server_hardware_uuid=SERVER_HARDWARE_UUID,
            vnic_type=VNIC_TYPE_BAREMETAL
        )
        session = context._plugin_context._session

        neutron_oneview_port = oneview_network_db.NeutronOneviewPort(
            PORT_ID, server_profile_uuid, conn_id
        )
        server_hardware = models.ServerHardware()
        server_hardware.server_profile_uri = server_profile_uri

        mock_get_neutron_oneview_port.return_value = neutron_oneview_port
        mock_sh_get.return_value = server_hardware
        mock_generate_connection_port_for_mac.return_value = 'port'

        self.driver.update_port_postcommit(context)

        mock_get_neutron_oneview_port.assert_called_once_with(
            session, PORT_ID
        )
        mock_sh_get.assert_called_once_with(
            self.driver.oneview_client.server_hardware, SERVER_HARDWARE_UUID
        )
        mock_update_connection.assert_called_once_with(
            self.driver.oneview_client.server_profile,
            server_profile_uuid,
            neutron_oneview_port.oneview_connection_id, new_boot_priority,
            'port'
        )
