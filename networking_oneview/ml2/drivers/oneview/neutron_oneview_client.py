import abc
import six
import utils


from neutron._i18n import _LW
from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from oslo_config import cfg


CONF = cfg.CONF

NETWORK_TYPE_FLAT = 'flat'
FLAT_NET = '0'
UPLINKSET = '1'
NETWORK_IS_NONE = '2'


@six.add_metaclass(abc.ABCMeta)
class ResourceManager:
    def __init__(self, oneview_client):
        self.oneview_client = oneview_client


class Network(ResourceManager):
    def add_network_to_uplinksets(
        self, uplinksets_id_list, oneview_network_uri
    ):
        for uplinkset_id in uplinksets_id_list:
            uplinkset = self.oneview_client.uplink_sets.get(uplinkset_id)
            uplinkset['networkUris'].append(oneview_network_uri)
            self.oneview_client.uplink_sets.update(uplinkset)

    def get_network_oneview_id(
        self, session, neutron_network_id, physical_network,
        oneview_network_mapping_dict
    ):
        network_id = oneview_network_mapping_dict.get(physical_network)
        if network_id:
            return network_id

        return db_manager.get_neutron_oneview_network(
            session, neutron_network_id
        )

    def verify_mapping_type(
        self, physical_network, uplinkset_mappings_dict,
        oneview_network_mapping_dict
    ):
        if physical_network in oneview_network_mapping_dict:
            return FLAT_NET

        if physical_network in uplinkset_mappings_dict:
            return UPLINKSET

        return NETWORK_IS_NONE

    def create(
        self, session, neutron_network_dict, uplinkset_id_list,
        oneview_network_mapping_dict, uplinkset_mappings_dict,
        commit, manageable=True
    ):
        """Create a Network resource on OneView and populates the database.

        This function will create a Ethernet Network resource on OneView using
        data from Neutron Network and then populates a table on Neutron side
        mapping the Neutron Network with the OneView Ethernet Network.
        """

        neutron_network_id = neutron_network_dict.get('id')
        neutron_network_name = neutron_network_dict.get('name')
        neutron_network_seg_id = neutron_network_dict.get(
            'provider:segmentation_id'
        )

        physical_network = neutron_network_dict.get(
            'provider:physical_network'
        )

        provider_network = neutron_network_dict.get('provider:network_type')

        oneview_network_uuid = self.get_network_oneview_id(
            session, neutron_network_id, physical_network,
            oneview_network_mapping_dict
        )
        verify_mapping = self.verify_mapping_type(
            physical_network, uplinkset_mappings_dict,
            oneview_network_mapping_dict
        )

        if verify_mapping is FLAT_NET:
            return self.map_add_neutron_network_to_oneview_network_in_database(
                session, neutron_network_id, oneview_network_uuid,
                uplinkset_id_list, commit, manageable=False
            )

        if oneview_network_uuid is None:
            net_type = 'Tagged' if neutron_network_seg_id else 'Untagged'
            options = {
                'name': "Neutron["+neutron_network_id+"]",
                'ethernetNetworkType': net_type,
                'vlanId': neutron_network_seg_id,
                "purpose": "General",
                "smartLink": False,
                "privateNetwork": False,
            }
            if net_type == 'Tagged':
                options['vlanId'] = neutron_network_seg_id
            oneview_network = self.oneview_client.ethernet_networks.create(
                options
            )
        self.add_network_to_uplinksets(
            uplinkset_id_list, oneview_network.get('uri')
        )

        self.map_add_neutron_network_to_oneview_network_in_database(
            session, neutron_network_id,
            utils.id_from_uri(oneview_network.get('uri')),
            uplinkset_id_list, commit, manageable=True
        )

    def map_add_neutron_network_to_oneview_network_in_database(
        self, session, neutron_network_id, oneview_network_id,
        uplinksets_id_list, commit, manageable=True
    ):
        db_manager.insert_neutron_oneview_network(
            session, neutron_network_id, oneview_network_id, commit, manageable
        )

        for uplinkset_id in uplinksets_id_list:
            db_manager.insert_oneview_network_uplinkset(
                session, oneview_network_id, uplinkset_id
            )

    def _remove_inconsistence_from_db(
        self, session, neutron_network_uuid, oneview_network_uuid, commit=False
    ):
        db_manager.delete_neutron_oneview_network(
            session, neutron_network_uuid, commit
        )

        db_manager.delete_oneview_network_uplinkset_by_network(
            session, oneview_network_uuid, commit
        )

    def delete(
        self, session, neutron_network_dict, oneview_network_mapping_dict
    ):
        neutron_network_id = neutron_network_dict.get('id')
        neutron_network_name = neutron_network_dict.get('name')
        neutron_network_seg_id = neutron_network_dict.get(
            'provider:segmentation_id'
        )
        physical_network = neutron_network_dict.get(
            'provider:physical_network'
        )
        provider_network = neutron_network_dict.get('provider:network_type')

        oneview_network_id = self.get_network_oneview_id(
            session, neutron_network_id, physical_network,
            oneview_network_mapping_dict
        )

        check_manageable = db_manager.get_manegement_neutron_network(
            session, neutron_network_id
            )

        if check_manageable.manageable:
            neutron_oneview_network = db_manager.get_neutron_oneview_network(
                session, neutron_network_id
            )

            oneview_network_id = neutron_oneview_network.oneview_network_uuid
            self.oneview_client.ethernet_networks.delete(
                self.oneview_client.ethernet_networks.get(
                    neutron_oneview_network.oneview_network_uuid
                )
            )

            for port in db_manager.list_port_with_network(
                session, neutron_network_id
            ):
                neutron_oneview_port = db_manager.get_neutron_oneview_port(
                    session, port.id
                )
                sp_id = neutron_oneview_port.oneview_server_profile_uuid
                conn_id = neutron_oneview_port.oneview_connection_id

                self._remove_connection(sp_id, conn_id)

                db_manager.delete_neutron_oneview_port(session, port.id)

        self._remove_inconsistence_from_db(
            session, neutron_network_id, oneview_network_id
        )

    def _remove_connection(self, server_profile_id, connection_id):
        server_profile = self.oneview_client.server_profiles.get(
            server_profile_id
        )

        connections = []
        for connection in server_profile.get('connections'):
            if connection.get('id') != connection_id:
                connections.append(connection)

        server_profile_to_update = server_profile.copy()
        server_profile_to_update['connections'] = connections

        self.oneview_client.server_profile.update(
            resource=server_profile_to_update,
            id_or_uri=server_profile_to_update.get('uri')
        )

    def update(
        self, session, neutron_network_id, new_network_name, physical_network,
        uplinkset_mappings_dict, oneview_network_mapping_dict
    ):
        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, neutron_network_id
        )
        if neutron_oneview_network is None:
            return

        verify_mapping = self.verify_mapping_type(
            physical_network, uplinkset_mappings_dict,
            oneview_network_mapping_dict
        )

        try:
            if verify_mapping is not FLAT_NET:
                network = self.oneview_client.ethernet_networks.get(
                    neutron_oneview_network.oneview_network_uuid
                )
                network['name'] = new_network_name
                self.oneview_client.ethernet_networks.update(network)

        except Exception:
            self._remove_inconsistence_from_db(
                session, neutron_network_id,
                neutron_oneview_network.oneview_network_uuid
            )
            LOG.warning(_LW("No mapped Network in Oneview"))


class Port(ResourceManager):
    def create(
        self, session, neutron_port_uuid, neutron_network_id, mac_address,
        local_link_information_dict
    ):
        switch_info_dict = local_link_information_dict.get('switch_info')
        server_hardware_uuid = switch_info_dict.get('server_hardware_uuid')
        boot_priority = switch_info_dict.get('boot_priority')

        server_hardware = self.oneview_client.server_hardware.get(
            server_hardware_uuid
        )

        server_profile_uri = utils.id_from_uri(
            server_hardware.get('serverProfileUri')
        )

        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, neutron_network_id
        )
        previous_power_state = self.get_server_hardware_power_state(
            server_hardware_uuid
        )
        self.update_server_hardware_power_state(server_hardware_uuid, "Off")

        connection_id = self._add_connection(
            server_profile_uri,
            self._generate_connection_port_for_mac(
                server_hardware, mac_address
            ),
            utils.uri_from_id(
                '/rest/ethernet-networks/',
                neutron_oneview_network.oneview_network_uuid
            ), boot_priority
        )

        db_manager.insert_neutron_oneview_port(
            session, neutron_port_uuid, server_profile_uri, connection_id
        )

        self.update_server_hardware_power_state(
            server_hardware_uuid, previous_power_state
        )

    def get_server_hardware_power_state(self, server_hardware_id):
        server_hardware_dict = self.oneview_client.server_hardware.get(
            server_hardware_id
        )
        return server_hardware_dict.get('powerState')

    def update_server_hardware_power_state(self, server_hardware_id, state):
            configuration = {
                "powerState": state,
                "powerControl": "MomentaryPress"
            }
            server_power = (
                self.oneview_client.server_hardware.update_power_state(
                    configuration, server_hardware_id
                )
            )

    def _generate_connection_port_for_mac(self, server_hardware, mac_address):
        port_info = self._get_connection_port_info(
            server_hardware, mac_address
        )
        return str(port_info.get('device_slot_location')) + " " +\
            str(port_info.get('device_slot_port_number')) + ":" +\
            str(port_info.get('physical_port_number')) + "-" +\
            str(port_info.get('virtual_port_function'))

    def _get_connection_port_info(self, server_hardware, mac_address):
        port_map = server_hardware.get('portMap')
        device_slots = port_map.get('deviceSlots')

        for device_slot in device_slots:
            physical_ports = device_slot.get('physicalPorts')
            for physical_port in physical_ports:
                virtual_ports = physical_port.get('virtualPorts')
                for virtual_port in virtual_ports:
                    mac = virtual_port.get('mac')
                    if mac == mac_address:
                        info_dict = {
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
                        return info_dict

    def _add_connection(
        self, server_profile_id, port_id, network_uri, boot_priority
    ):
        def get_next_connection_id(server_profile):
            next_id = 0
            for connection in server_profile.get('connections'):
                if connection.get('id') > next_id:
                    next_id = connection.get('id')
            return next_id + 1

        server_profile = self.oneview_client.server_profiles.get(
            server_profile_id
        ).copy()

        connection_id = get_next_connection_id(server_profile)
        server_profile['connections'].append({
            'portId': port_id,
            'networkUri': network_uri,
            'boot': {'priority': boot_priority},
            'functionType': 'Ethernet',
            'id': connection_id
        })

        self.oneview_client.server_profiles.update(
            resource=server_profile,
            id_or_uri=server_profile.get('uri')
        )

        return connection_id

    def update(
        self, session, neutron_port_uuid, lli_dict, port_boot_priority,
        port_mac_address
    ):
        neutron_oneview_port = db_manager.get_neutron_oneview_port(
            session, neutron_port_uuid
        )
        server_hardware = self.oneview_client.server_hardware.get(
            common.server_hardware_from_local_link_information(lli_dict)
        )
        server_profile_uuid = utils.id_from_uri(
            server_hardware.get('serverProfileUri')
        )

        return self._update_connection(
            server_profile_uuid,
            neutron_oneview_port.oneview_connection_id,
            self._generate_connection_port_for_mac(
                server_hardware, port_mac_address
            ),
            port_boot_priority
        )

    def _update_connection(
        self, server_profile_id, connection_id, port_id, boot_priority
    ):
        server_profile = self.oneview_client.server_profiles.get(
            server_profile_id
        ).copy()

        for connection in server_profile.get('connections'):
            if int(connection.get('id')) == int(connection_id):
                connection['portId'] = port_id
                connection['boot'] = {'priority': boot_priority}

        self.oneview_client.server_profiles.update(
            resource=server_profile,
            id_or_uri=server_profile.get('uri')
        )
        return connection_id

    def delete(self, session, neutron_port_uuid, server_hardware_uuid):
        neutron_oneview_port=db_manager.get_neutron_oneview_port(
            session, neutron_port_uuid
        )
        server_hardware=self.oneview_client.server_hardware.get(
            server_hardware_uuid
        )
        previous_power_state=self.get_server_hardware_power_state(
            server_hardware_uuid
        )
        self.update_server_hardware_power_state(server_hardware_uuid, "Off")

        if neutron_oneview_port:
            self._delete_connection(
                neutron_oneview_port.oneview_server_profile_uuid,
                neutron_oneview_port.oneview_connection_id
            )
            db_manager.delete_neutron_oneview_port(session, neutron_port_uuid)

        self.update_server_hardware_power_state(
            server_hardware_uuid, previous_power_state
        )

    def _delete_connection(self, server_profile_id, connection_id):
        server_profile=self.oneview_client.server_profiles.get(
            server_profile_id
        ).copy()

        connections=[]
        for connection in server_profile.get('connections'):
            if int(connection.get('id')) != int(connection_id):
                connections.append(connection)

        server_profile['connections']=connections

        self.oneview_client.server_profiles.update(
            resource=server_profile,
            id_or_uri=server_profile.get('uri')
        )


class UplinkSet(ResourceManager):
    neutron_net_type_to_oneview_net_type = {
        'vxlan': 'Tagged',
        'vlan': 'Tagged',
        'flat': 'Untagged',
    }

    def filter_by_type(self, uplinkset_list, network_type):
        uplinkset_by_type = []
        if uplinkset_list is None or len(uplinkset_list) == 0:
            return uplinkset_by_type

        oneview_net_type = self.neutron_net_type_to_oneview_net_type.get(
            network_type
        )

        for uplinkset_uuid in uplinkset_list:
            uplinkset = self.oneview_client.uplink_sets.get(uplinkset_uuid)
            if uplinkset.get('ethernetNetworkType') == oneview_net_type:
                uplinkset_by_type.append(uplinkset_uuid)

        return uplinkset_by_type

    def remove_network(self, session, uplinkset_id, network_id):
        self.oneview_client.uplink_sets.remove_ethernet_networks(
            uplinkset_id, network_id
        )
        db_manager.delete_oneview_network_uplinkset(
            session, uplinkset_id, network_id
        )

    def add_network(self, session, uplinkset_id, network_id):
        uplinkset = self.oneview_client.uplink_sets.get(uplinkset_id)
        network_uri = "/rest/ethernet-networks/" + network_id

        if network_uri not in uplinkset['networkUris']:
            uplinkset['networkUris'].append(network_uri)
            self.oneview_client.uplink_sets.update(uplinkset)
            db_manager.insert_oneview_network_uplinkset(
                session, network_id, uplinkset_id
            )


class Client:
    def __init__(self, oneview_client):
        self.network = Network(oneview_client)
        self.port = Port(oneview_client)
        self.uplinkset = UplinkSet(oneview_client)
