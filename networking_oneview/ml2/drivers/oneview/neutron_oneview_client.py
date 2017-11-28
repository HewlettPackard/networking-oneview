# Copyright (2016-2017) Hewlett Packard Enterprise Development LP.
# Copyright (2016-2017) Universidade Federal de Campina Grande
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

import abc
import six
import time

from hpOneView import exceptions
from oslo_log import log
from oslo_utils import strutils

from networking_oneview.ml2.drivers.oneview import (
    database_manager as db_manager)
from networking_oneview.ml2.drivers.oneview import common

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class ResourceManager(object):
    def __init__(self, oneview_client, uplinkset_mappings, flat_net_mappings):
        self.oneview_client = oneview_client
        self.uplinkset_mappings = uplinkset_mappings
        self.flat_net_mappings = flat_net_mappings

    def is_uplinkset_mapping(self, physical_network, network_type):
        if self._is_physnet_in_uplinkset_mapping(
            physical_network, network_type
        ):
            return True

        if self.flat_net_mappings.get(physical_network):
            return True

        return False

    def _is_physnet_in_uplinkset_mapping(self, physical_network, network_type):
        network_type = (
            common.NETWORK_TYPE_UNTAGGED if network_type == 'flat' else (
                common.NETWORK_TYPE_TAGGED
            )
        )
        if self.uplinkset_mappings.get(network_type).get(physical_network):
            return True

        return False

    def check_server_hardware_availability(self, server_hardware):
        while True:
            if not server_hardware.get('powerLock'):
                return True
            time.sleep(30)

    def check_server_profile_availability(self, server_hardware):
        while True:
            if self.get_server_profile_state(server_hardware):
                return True
            time.sleep(5)

    def get_server_profile_state(self, server_hardware):
        server_profile_dict = self.server_profile_from_server_hardware(
            server_hardware
        )
        return server_profile_dict.get('status')

    def get_server_hardware_power_state(self, server_hardware):
        return server_hardware.get('powerState')

    def update_server_hardware_power_state(self, server_hardware, state):
        configuration = {
            "powerState": state,
            "powerControl": "MomentaryPress"
        }
        server_hardware_id = server_hardware.get('uuid')

        self.oneview_client.server_hardware.update_power_state(
            configuration, server_hardware_id
        )

    def server_profile_from_server_hardware(self, server_hardware):
        server_profile_uri = server_hardware.get('serverProfileUri')
        if server_profile_uri:
            LOG.info(
                "There is Server Profile %s available.", server_profile_uri)
            return self.oneview_client.server_profiles.get(
                server_profile_uri)
        else:
            LOG.warning("There is no Server Profile available.")


class Network(ResourceManager):
    NEUTRON_NET_TYPE_TO_ONEVIEW_NET_TYPE = {
        'vxlan': 'tagged',
        'vlan': 'tagged',
        'flat': 'untagged',
    }

    def create(self, session, network_dict):
        network_id = network_dict.get('id')
        network_seg_id = network_dict.get('provider:segmentation_id')
        physical_network = network_dict.get('provider:physical_network')
        network_type = network_dict.get('provider:network_type')
        mapping_type = self._get_network_mapping_type(
            physical_network, network_type
        )

        if not self.is_uplinkset_mapping(physical_network, network_type):
            LOG.warning(
                "The network %s is not mapped in OneView "
                "configuration file.", network_id)
            return

        if db_manager.get_neutron_oneview_network(session, network_id):
            LOG.warning(
                "The network %s is already created.", network_id)
            return

        if not mapping_type:
            LOG.warning(
                "The network: %s type is not supported.", network_id)
            return

        mappings = []
        oneview_network_id = None
        if mapping_type == common.UPLINKSET_MAPPINGS_TYPE:
            network_type = 'tagged' if network_seg_id else 'untagged'
            oneview_network = self._create_network_on_oneview(
                name="Neutron [" + network_id + "]",
                network_type=network_type.capitalize(), seg_id=network_seg_id)
            oneview_network_id = common.id_from_uri(oneview_network.get('uri'))
            mappings = self._add_to_ligs(
                network_type, physical_network, oneview_network)
        elif mapping_type == common.FLAT_NET_MAPPINGS_TYPE:
            oneview_network_id = self.flat_net_mappings.get(physical_network)
        # BUG(nicodemos) This is not reachable. see: line 126
        else:
            LOG.warning("Network Type unsupported")

        db_manager.map_neutron_network_to_oneview(
            session, network_id, oneview_network_id,
            mapping_type == common.UPLINKSET_MAPPINGS_TYPE, mappings)

        LOG.info("Network %s created.", network_id)

    def _get_network_mapping_type(self, physical_network, network_type):
        physnet_in_uplinkset_mapping = self._is_physnet_in_uplinkset_mapping(
            physical_network, network_type
        )
        if network_type == 'vlan' and physnet_in_uplinkset_mapping:
            return common.UPLINKSET_MAPPINGS_TYPE
        elif physical_network in self.flat_net_mappings:
            return common.FLAT_NET_MAPPINGS_TYPE
        # BUG(nicodemos) if a network provider:physical_network is mapped
        # in uplinkset_mappings and using any 'provider:network_type' != flat
        # we return this.
        # NOTE(nicodemos) adding network_type == 'flat' is the rigth call?
        elif network_type == 'flat' and physnet_in_uplinkset_mapping:
            return common.UPLINKSET_MAPPINGS_TYPE

        return common.MAPPING_TYPE_NONE

    def _get_lig_list(self, physical_network, network_type):
        mappings_by_type = self.uplinkset_mappings.get(network_type)
        mappings_by_physical_network = mappings_by_type.get(physical_network)
        return mappings_by_physical_network

    def _get_uplinksets_from_lig(self, network_type, lig_list):
        lig_ids = lig_list[0::2]
        uplinksets = []

        for uplink_name in lig_list[1::2]:
            uplinks = self.oneview_client.uplink_sets.get_by(
                'name', uplink_name
            )
            for uplink in uplinks:
                logical_interconnect = (
                    self.oneview_client.logical_interconnects.get(
                        uplink.get('logicalInterconnectUri')
                    )
                )
                logical_interconnect_group_id = common.id_from_uri(
                    logical_interconnect.get('logicalInterconnectGroupUri')
                )
                if logical_interconnect_group_id in lig_ids and uplink.get(
                        'ethernetNetworkType').lower() == network_type:
                    uplinksets.append(uplink)
        return uplinksets

    def _create_network_on_oneview(self, name, network_type, seg_id):
        options = {
            'name': name,
            'ethernetNetworkType': network_type,
            'vlanId': seg_id,
            'purpose': 'General',
            'smartLink': False,
            'privateNetwork': False,
        }
        return self.oneview_client.ethernet_networks.create(options)

    def _add_network_to_logical_interconnect_group(
        self, uplinkset_mappings, network_uri
    ):
        for lig_id, uplinkset_name in zip(
            uplinkset_mappings[0::2], uplinkset_mappings[1::2]
        ):
            logical_interconnect_group = (
                common.get_logical_interconnect_group_by_id(
                    self.oneview_client, lig_id
                )
            )
            lig_uplinksets = logical_interconnect_group.get('uplinkSets')
            uplinkset = common.get_uplinkset_by_name_from_list(
                lig_uplinksets, uplinkset_name
            )
            if network_uri not in uplinkset['networkUris']:
                uplinkset['networkUris'].append(network_uri)
                self.oneview_client.logical_interconnect_groups.update(
                    logical_interconnect_group
                )

    def _add_network_to_logical_interconnects(
        self, uplinkset_list, network_uri
    ):
        for uplinkset in uplinkset_list:
            if network_uri not in uplinkset['networkUris']:
                uplinkset['networkUris'].append(network_uri)
                self.oneview_client.uplink_sets.update(uplinkset)

    def delete(self, session, network_dict):
        network_id = network_dict.get('id')
        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, network_id
        )
        if neutron_oneview_network is None:
            return

        oneview_network_id = neutron_oneview_network.oneview_network_id
        if neutron_oneview_network.manageable:
            self.oneview_client.ethernet_networks.delete(oneview_network_id)

        db_manager.delete_neutron_oneview_network(
            session, neutron_network_id=network_id
        )
        db_manager.delete_oneview_network_lig(
            session, oneview_network_id=oneview_network_id
        )
        LOG.info("Network %s deleted", oneview_network_id)

    def update_network_lig(
        self, session, oneview_network_id, network_type, physical_network
    ):
        network_type = self.NEUTRON_NET_TYPE_TO_ONEVIEW_NET_TYPE.get(
            network_type)
        mappings = self.uplinkset_mappings.get(network_type).get(
            physical_network)
        if mappings is None:
            mappings = []
        mapped_ligs = db_manager.list_oneview_network_lig(
            session, oneview_network_id=oneview_network_id)
        for lig_bd_entry in mapped_ligs:
            if not self._is_lig_id_uplink_name_mapped(lig_bd_entry, mappings):
                self._remove_network_from_lig_and_lis(
                    oneview_network_id,
                    lig_bd_entry.get('oneview_lig_id'),
                    lig_bd_entry.get('oneview_uplinkset_name'), network_type
                )
                db_manager.delete_oneview_network_lig(
                    session, oneview_network_id=oneview_network_id,
                    oneview_lig_id=lig_bd_entry.get('oneview_lig_id'),
                    oneview_uplinkset_name=lig_bd_entry.get(
                        'oneview_uplinkset_name'))
        self._add_to_ligs(
            network_type, physical_network,
            self.oneview_client.ethernet_networks.get(oneview_network_id))
        for lig_id, uplinkset_name in zip(mappings[0::2], mappings[1::2]):
            network_mapped = db_manager.get_oneview_network_lig(
                session,
                oneview_network_id=oneview_network_id,
                oneview_lig_id=lig_id,
                oneview_uplinkset_name=uplinkset_name)
            if not network_mapped:
                db_manager.insert_oneview_network_lig(
                    session, oneview_network_id, lig_id, uplinkset_name
                )

    def _is_lig_id_uplink_name_mapped(self, lig_bd_entry, mappings):
        mapped_lig_id = lig_bd_entry.get('oneview_lig_id')
        mapped_uplink_name = lig_bd_entry.get('oneview_uplinkset_name')
        for lig_id, uplinkset_name in zip(mappings[0::2], mappings[1::2]):
            if lig_id == mapped_lig_id and (
                    uplinkset_name == mapped_uplink_name):
                return True
        return False

    def _add_to_ligs(self, network_type, physical_network, oneview_network):
        lig_list = self._get_lig_list(physical_network, network_type)
        uplinksets_list = self._get_uplinksets_from_lig(
            network_type, lig_list)
        self._add_network_to_logical_interconnect_group(
            lig_list, oneview_network.get('uri'))
        self._add_network_to_logical_interconnects(
            uplinksets_list, oneview_network.get('uri')
        )
        return lig_list

    def _remove_network_from_lig_and_lis(
            self, network_id, lig_id, uplinkset_name, network_type):
        mapping = [lig_id, uplinkset_name]
        lig = self.oneview_client.logical_interconnect_groups.get(lig_id)
        lig_uplinksets = lig.get('uplinkSets')
        uplinkset = common.get_uplinkset_by_name_from_list(
            lig_uplinksets, uplinkset_name
        )
        uplinkset['networkUris'].remove(
            '/rest/ethernet-networks/' + network_id)
        self.oneview_client.logical_interconnect_groups.update(
            lig
        )
        uplinksets_list = self._get_uplinksets_from_lig(network_type, mapping)
        uplinksets_uri_list = (
            uplinkset.get('uri') for uplinkset in uplinksets_list)
        self._remove_network_from_uplink_sets(network_id, uplinksets_uri_list)

    def _remove_network_from_uplink_sets(self, network_id, uplinksets_id_list):
        if not uplinksets_id_list:
            return

        uplinksets_id_list = list(uplinksets_id_list)
        for uplinkset_id in uplinksets_id_list:
            self.oneview_client.uplink_sets.remove_ethernet_networks(
                uplinkset_id, network_id
            )

    def _add_network_to_uplink_sets(self, network_id, uplinksets_id_list):
        if not uplinksets_id_list:
            return

        uplinksets_id_list = list(uplinksets_id_list)
        for uplinkset_id in uplinksets_id_list:
            try:
                self.oneview_client.uplink_sets.add_ethernet_networks(
                    uplinkset_id, network_id
                )
            except exceptions.HPOneViewException as err:
                LOG.error(
                    "Driver couldn't add network %(network_id)s to uplink set "
                    "%(uplink_set_id)s. %(error)s" % {
                        'network_id': network_id,
                        'uplink_set_id': uplinkset_id,
                        'error': err
                    }
                )


class Port(ResourceManager):
    def create(self, session, port_dict):
        network_id = port_dict.get('network_id')
        neutron_port_id = port_dict.get('id')

        network_segment = db_manager.get_network_segment(session, network_id)
        physical_network = network_segment.get('physical_network')
        network_type = network_segment.get('network_type')

        if not self.is_uplinkset_mapping(physical_network, network_type):
            LOG.warning(
                "The port's network %s is not mapping in OneView "
                "configuration file", network_id)
            return
        local_link_information_list = common.local_link_information_from_port(
            port_dict
        )

        if not self._is_port_valid_to_reflect_on_oneview(
            session, port_dict, local_link_information_list
        ):
            LOG.warning(
                "Port %s is not valid to reflect on OneView.", neutron_port_id
            )
            return
        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, network_id)
        network_uri = common.network_uri_from_id(
            neutron_oneview_network.oneview_network_id)
        switch_info = common.switch_info_from_local_link_information_list(
            local_link_information_list)
        server_hardware = (
            common.server_hardware_from_local_link_information_list(
                self.oneview_client, local_link_information_list))
        server_profile = self.server_profile_from_server_hardware(
            server_hardware
        )
        if server_profile:
            LOG.info("There is Server Profile %s available.", server_profile)
            bootable = switch_info.get('bootable')
            mac_address = port_dict.get('mac_address')
            if common.is_rack_server(server_hardware):
                LOG.warning("The server hardware %s is a rack server.",
                            server_hardware.get('uuid'))
                return

            port_id = self._port_id_from_mac(server_hardware, mac_address)
            connections = server_profile.get('connections')
            existing_connections = [connection for connection in connections
                                    if connection.get('portId') == port_id]
            boot_priority = self._get_boot_priority(server_profile, bootable)

            create_new_connection = True
            for connection in existing_connections:
                if connection.get('mac').upper() == mac_address.upper():
                    connection['networkUri'] = network_uri
                    create_new_connection = False
            if create_new_connection:
                server_profile['connections'].append({
                    'name': "NeutronPort[%s]" % mac_address,
                    'portId': port_id,
                    'networkUri': network_uri,
                    'boot': {'priority': boot_priority},
                    'functionType': 'Ethernet'
                })

            self._check_oneview_entities_availability(server_hardware)
            self._update_oneview_entities(server_hardware, server_profile)
            LOG.info("The requested connection %s was updated/created.",
                     port_id)

    def _get_boot_priority(self, server_profile, bootable):
        if bootable:
            connections = server_profile.get('connections')
            if self._is_boot_priority_available(connections, 'Primary'):
                return 'Primary'
            elif self._is_boot_priority_available(connections, 'Secondary'):
                return 'Secondary'
        return 'NotBootable'

    def _is_boot_priority_available(self, connections, boot_priority):
        for connection in connections:
            if connection.get('boot').get('priority') == boot_priority:
                return False
        return True

    def _port_id_from_mac(self, server_hardware, mac_address):
        port_info = self._get_port_info(server_hardware, mac_address)

        return (
            str(port_info.get('device_slot_location')) + " " +
            str(port_info.get('device_slot_port_number')) + ":" +
            str(port_info.get('physical_port_number')) + "-" +
            str(port_info.get('virtual_port_function'))
        )

    def _get_port_info(self, server_hardware, mac_address):
        port_map = server_hardware.get('portMap')
        device_slots = port_map.get('deviceSlots')

        for device_slot in device_slots:
            physical_ports = device_slot.get('physicalPorts')
            for physical_port in physical_ports:
                virtual_ports = physical_port.get('virtualPorts')
                for virtual_port in virtual_ports:
                    mac = virtual_port.get('mac')
                    if mac.upper() == mac_address.upper():
                        return {
                            'virtual_port_function': virtual_port.get(
                                'portFunction'
                            ),
                            'physical_port_number': physical_port.get(
                                'portNumber'
                            ),
                            'device_slot_port_number': device_slot.get(
                                'slotNumber'
                            ),
                            'device_slot_location': device_slot.get(
                                'location'
                            ),
                        }

    def delete(self, session, port_dict):
        local_link_information_list = common.local_link_information_from_port(
            port_dict
        )
        neutron_port_id = port_dict.get('id')

        if not self._is_port_valid_to_reflect_on_oneview(
            session, port_dict, local_link_information_list
        ):
            LOG.warning(
                "Port %s is not valid to reflect on OneView.", neutron_port_id
            )
            return

        server_hardware = (
            common.server_hardware_from_local_link_information_list(
                self.oneview_client, local_link_information_list))
        server_profile = self.server_profile_from_server_hardware(
            server_hardware
        )
        if server_profile:
            LOG.info("There is Server Profile %s available.", server_profile)
            mac_address = port_dict.get('mac_address')
            connection = self._connection_with_mac_address(
                server_profile.get('connections'), mac_address
            )
            if connection:
                LOG.debug("There is Connection %s available.", connection)
                server_profile.get('connections').remove(connection)
            else:
                LOG.debug("There is no Connection available.")

            self._check_oneview_entities_availability(server_hardware)
            self._update_oneview_entities(server_hardware, server_profile)
            LOG.info("The requested port was deleted successfully.")

    def _connection_with_mac_address(self, connections, mac_address):
        for connection in connections:
            if connection.get('mac') == mac_address:
                return connection

    def _is_port_valid_to_reflect_on_oneview(
        self, session, port_dict, local_link_information_list
    ):
        def is_local_link_information_valid(local_link_information_list):
            if not local_link_information_list:
                LOG.warning(
                    "The port %s must have 'local_link_information'" % port_id)
                return False

            if len(local_link_information_list) > 1:
                LOG.warning(
                    "'local_link_information' must have only one value")
                return False

            switch_info = common.switch_info_from_local_link_information_list(
                local_link_information_list)

            if not switch_info:
                LOG.warning(
                    "'local_link_information' must contain 'switch_info'.")
                return False

            server_hardware_id = switch_info.get('server_hardware_id')

            try:
                bootable = strutils.bool_from_string(
                    switch_info.get('bootable'))
            except Exception:
                LOG.warning("'bootable' must be a boolean.")
                return False

            if not (server_hardware_id and bootable):
                LOG.warning(
                    "'local_link_information' must contain "
                    "'server_hardware_id' and 'bootable'.")
                return False

            return True

        vnic_type = port_dict.get('binding:vnic_type')
        port_id = port_dict.get("id")
        if vnic_type != 'baremetal':
            LOG.warning("'vnic_type' of the port %s must be baremetal" %
                        port_id)
            return False

        network_id = port_dict.get('network_id')
        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, network_id
        )
        if not neutron_oneview_network:
            LOG.warning(
                "There is no network created for the port %s" % port_id)
            return False

        return is_local_link_information_valid(local_link_information_list)

    def _check_oneview_entities_availability(self, server_hardware):
        self.check_server_profile_availability(server_hardware)
        self.check_server_hardware_availability(server_hardware)

    def _update_oneview_entities(self, server_hardware, server_profile):
        previous_power_state = self.get_server_hardware_power_state(
            server_hardware
        )
        self.update_server_hardware_power_state(
            server_hardware, "Off"
        )
        self.oneview_client.server_profiles.update(
            resource=server_profile,
            id_or_uri=server_profile.get('uri')
        )
        self.update_server_hardware_power_state(
            server_hardware, previous_power_state
        )


class Client(object):
    def __init__(self, oneview_client, uplinkset_mappings, flat_net_mappings):
        self.oneview_client = oneview_client
        self.uplinkset_mappings = self._uplinkset_mappings_by_type(
            uplinkset_mappings
        )
        self.network = Network(
            self.oneview_client, self.uplinkset_mappings, flat_net_mappings
        )
        self.port = Port(
            self.oneview_client, self.uplinkset_mappings, flat_net_mappings
        )

    def _uplinkset_mappings_by_type(self, uplinkset_mappings):
        uplinkset_mappings_by_type = {}

        uplinkset_mappings_by_type[common.NETWORK_TYPE_TAGGED] = (
            self._get_uplinkset_by_type(
                uplinkset_mappings,
                common.NETWORK_TYPE_TAGGED
            )
        )

        uplinkset_mappings_by_type[common.NETWORK_TYPE_UNTAGGED] = (
            self._get_uplinkset_by_type(
                uplinkset_mappings,
                common.NETWORK_TYPE_UNTAGGED
            )
        )

        return uplinkset_mappings_by_type

    def _get_uplinkset_by_type(self, uplinkset_mappings, net_type):
        uplinksets_by_type = {}

        for physnet in uplinkset_mappings:
            provider = uplinkset_mappings.get(physnet)
            for lig_id, uplinkset_name in zip(provider[0::2], provider[1::2]):
                lig = common.get_logical_interconnect_group_by_id(
                    self.oneview_client, lig_id)
                lig_uplinksets = lig.get('uplinkSets')

                uplinkset = common.get_uplinkset_by_name_from_list(
                    lig_uplinksets, uplinkset_name
                )
                if uplinkset.get('ethernetNetworkType').lower() == net_type:
                    uplinksets_by_type.setdefault(physnet, []).extend(
                        [lig_id, uplinkset_name]
                    )
        return uplinksets_by_type
