import abc
import six

from neutron._i18n import _LW
from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from oneview_client import exceptions
from oneview_client import models
from oneview_client import utils
from oslo_config import cfg


CONF = cfg.CONF

NETWORK_TYPE_FLAT = 'flat'


@six.add_metaclass(abc.ABCMeta)
class ResourceManager:
    def __init__(self, oneview_client):
        self.oneview_client = oneview_client


class Network(ResourceManager):
    def add_network_to_uplinksets(
        self, uplinksets_id_list, oneview_network_id
    ):
        for uplinkset_id in uplinksets_id_list:
            self.oneview_client.uplinkset.add_network(
                uplinkset_id, oneview_network_id
            )

    def create(
        self, session, neutron_network_dict, uplinkset_id_list,
        oneview_network_mapping_dict
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

        oneview_network_uuid = self.get_mapped_oneview_network_uuid(
            oneview_network_mapping_dict, provider_network, physical_network,
            neutron_network_name
        )

        if oneview_network_uuid is None:
            kwargs = common.prepare_oneview_network_args(
                neutron_network_name, neutron_network_seg_id
            )
            oneview_network_uri = self.oneview_client.ethernet_network.create(
                **kwargs
            )

            oneview_network_id = utils.get_uuid_from_uri(oneview_network_uri)

            self.add_network_to_uplinksets(
                uplinkset_id_list, oneview_network_id
            )

        self.map_add_neutron_network_to_oneview_network_in_database(
            session, neutron_network_id, oneview_network_uuid,
            uplinkset_id_list
        )

    def get_mapped_oneview_network_uuid(
        self, oneview_network_mapping_dict, provider_network, physical_network,
        neutron_network_name
    ):
        if provider_network != NETWORK_TYPE_FLAT or physical_network is None:
            return None

        return oneview_network_mapping_dict.get(neutron_network_name)

    def map_add_neutron_network_to_oneview_network_in_database(
        self, session, neutron_network_id, oneview_network_id,
        uplinksets_id_list
    ):
        db_manager.insert_neutron_oneview_network(
            session, neutron_network_id, oneview_network_id
        )
        for uplinkset_id in uplinksets_id_list:
            db_manager.insert_oneview_network_uplinkset(
                session, oneview_network_id, uplinkset_id
            )

    def _remove_inconsistence_from_db(
        self, session, neutron_network_uuid, oneview_network_uuid
    ):
        db_manager.delete_neutron_oneview_network(
            session, neutron_network_uuid
        )
        db_manager.delete_oneview_network_uplinkset(
            session, oneview_network_uuid
        )

    def delete(
        self, session, neutron_network_dict, uplinksets_uuid_list,
        oneview_network_mapping_list
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

        oneview_network_uuid = self.get_mapped_oneview_network_uuid(
            oneview_network_mapping_list, provider_network, physical_network,
            neutron_network_name
        )

        if oneview_network_uuid is None:
            neutron_oneview_network = db_manager.get_neutron_oneview_network(
                session, neutron_network_id
            )
            oneview_network_uuid = neutron_oneview_network.oneview_network_uuid
            self.oneview_client.ethernet_network.delete(
                neutron_oneview_network.oneview_network_uuid
            )

        self.map_remove_neutron_network_to_oneview_network_in_database(
            session, neutron_network_id, oneview_network_uuid,
            uplinksets_uuid_list
        )

    def map_remove_neutron_network_to_oneview_network_in_database(
        self, session, neutron_network_id, oneview_network_uuid,
        uplinksets_uuid_list
    ):
        db_manager.delete_neutron_oneview_network(
            session, neutron_network_id
        )
        for uplinkset_uuid in uplinksets_uuid_list:
            db_manager.delete_oneview_network_uplinkset(
                session, oneview_network_uuid, uplinkset_uuid
            )

    def update(self, session, neutron_network_id, new_network_name):
        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, neutron_network_id
        )
        if neutron_oneview_network is None:
            return

        try:
            self.oneview_client.ethernet_network.update_name(
                neutron_oneview_network.oneview_network_uuid,
                new_network_name
            )
        except exceptions.OneViewResourceNotFoundError:
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

        server_profile_uuid = utils.get_uuid_from_uri(
            server_hardware.server_profile_uri
        )

        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, neutron_network_id
        )

        connection = self.oneview_client.server_profile.add_connection(
            server_profile_uuid,
            neutron_oneview_network.oneview_network_uuid, boot_priority,
            server_hardware.generate_connection_port_for_mac(mac_address)
        )

        db_manager.insert_neutron_oneview_port(
            session, neutron_port_uuid, server_profile_uuid,
            connection.get('id')
        )

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
        server_profile_uuid = utils.get_uuid_from_uri(
            server_hardware.server_profile_uri
        )

        return self.oneview_client.server_profile.update_connection(
            server_profile_uuid,
            neutron_oneview_port.oneview_connection_id, port_boot_priority,
            server_hardware.generate_connection_port_for_mac(port_mac_address)
        )

    def delete(self, session, neutron_port_uuid):
        neutron_oneview_port = db_manager.get_neutron_oneview_port(
            session, neutron_port_uuid
        )

        if neutron_oneview_port:
            self.oneview_client.server_profile.remove_connection(
                neutron_oneview_port.oneview_server_profile_uuid,
                neutron_oneview_port.oneview_connection_id
            )

            db_manager.delete_neutron_oneview_port(session, neutron_port_uuid)


class UplinkSet(ResourceManager):
    neutron_net_type_to_oneview_net_type = {
        'vxlan': 'Tagged',
        'vlan': 'Tagged',
        'flat': 'Untagged',
    }

    def get_uplinkset_by_type(self, uplinkset_list, network_type):
        uplinkset_by_type = []
        if uplinkset_list is None or len(uplinkset_list) == 0:
            return uplinkset_by_type

        oneview_net_type = self.neutron_net_type_to_oneview_net_type.get(
            network_type
        )
        for uplinkset_uuid in uplinkset_list:
            uplinkset = self.oneview_client.uplinkset.get(uplinkset_uuid)
            if uplinkset.ethernet_network_type == oneview_net_type:
                uplinkset_by_type.append(uplinkset_uuid)

        return uplinkset_by_type


class Client:
    def __init__(self, oneview_client):
        self.network = Network(oneview_client)
        self.port = Port(oneview_client)
        self.uplinkset = UplinkSet(oneview_client)
