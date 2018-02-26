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

import time

from itertools import chain
import six

from hpOneView.oneview_client import OneViewClient
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import importutils
from oslo_utils import strutils
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from networking_oneview.conf import CONF
from networking_oneview.ml2.drivers.oneview import database_manager
from networking_oneview.ml2.drivers.oneview import exceptions

MAPPING_TYPE_NONE = 0
FLAT_NET_MAPPINGS_TYPE = 1
UPLINKSET_MAPPINGS_TYPE = 2

NETWORK_TYPE_TAGGED = 'tagged'
NETWORK_TYPE_UNTAGGED = 'untagged'
ETHERNET_NETWORK_PREFIX = '/rest/ethernet-networks/'

LOG = log.getLogger(__name__)

oneview_exceptions = importutils.try_import('hpOneView.exceptions')


def get_oneview_conf():
    """Get OneView Access Configuration."""
    insecure = CONF.oneview.allow_insecure_connections
    ssl_certificate = CONF.oneview.tls_cacert_file

    if not (insecure or ssl_certificate):
        raise oneview_exceptions.HPOneViewException(
            "Failed to start Networking OneView. Attempting to open secure "
            "connection to OneView but CA certificate file is missing. Please "
            "check your configuration file.")

    if insecure:
        LOG.info("Networking OneView is opening an insecure connection to "
                 "HPE OneView. We recommend you to configure secure "
                 "connections with a CA certificate file.")

        if ssl_certificate:
            LOG.info("Insecure connection to OneView, the CA certificate: %s "
                     "will be ignored." % ssl_certificate)
            ssl_certificate = None

    oneview_conf = {
        "ip": CONF.oneview.oneview_host,
        "credentials": {
            "userName": CONF.oneview.username,
            "password": CONF.oneview.password
        },
        "ssl_certificate": ssl_certificate
    }

    return oneview_conf


def get_oneview_client():
    """Get the OneView Client."""
    LOG.debug("Creating a new OneViewClient instance.")
    try:
        client = OneViewClient(get_oneview_conf())
    except oneview_exceptions.HPOneViewException as ex:
        LOG.info("Networking OneView could not open a connection to "
                 "HPE OneView. Check credentials and/or CA certificate file. "
                 "See details on error below:\n")
        raise ex
    return client


def oneview_reauth(f):
    def wrapper(self, *args, **kwargs):
        try:
            self.oneview_client.connection.get('/rest/logindomains')
        except oneview_exceptions.HPOneViewException:
            LOG.debug("Reauthenticating to OneView.")
            oneview_conf = get_oneview_conf()
            self.oneview_client.connection.login(oneview_conf["credentials"])
        return f(self, *args, **kwargs)
    return wrapper


# Utils
def id_from_uri(uri):
    if not uri:
        return None
    return uri.split("/")[-1]


def id_list_from_uri_list(uri_list):
    return [id_from_uri(uri) for uri in uri_list]


def uplinksets_id_from_network_uplinkset_list(net_uplink_list):
    return [net_uplink.oneview_uplinkset_id for net_uplink in net_uplink_list]


def get_uplinkset_by_name_from_list(uplinkset_list, uplinkset_name):
    """Get the first uplinkset from a list that matches the name.

    Given a list of uplinksets, it retrieves the first uplinkset with
    the same name as uplinkset_name.

    :param uplinkset_list: a list of uplinksets;
    :param uplinkset_name: the name of the desired uplinkset;
    :returns: A uplinkset with name uplinkset_name
    :raise ElementNotFoundException: Uplinkset name not found in
        Uplinkset list;
    """
    try:
        uplinkset_obj = next(
            uplinkset for uplinkset in uplinkset_list if uplinkset.get(
                'name') == uplinkset_name)
    except Exception:
        err_msg = (
            "Uplinkset '%s' is not found in the Uplinkset List '%s'"
        ) % (uplinkset_name, uplinkset_list)
        LOG.error(err_msg)
        raise exceptions.ElementNotFoundException(err_msg)

    return uplinkset_obj


def get_uplinkset_by_name_in_lig(oneview_client, lig_id, uplinkset_name):
    """Get the uplinkset in a Logical Interconnect Group with that name.

    :param oneview_client: An instanciated oneview_client
    :param lig_id: The logical Interconnect Group ID
    :param uplinkset_name: The name of the uplinkset to be retrieved.
    :returns: The uplinkset from LIG
    """
    lig = oneview_client.logical_interconnect_groups.get(lig_id)
    uplinkset = (uls for uls in lig.get(
        'uplinkSets') if uls.get('name') == uplinkset_name).next()

    return uplinkset


def get_logical_interconnect_group_by_id(lig_id):
    """Get a Logical Interconnect Group Object to a given LIG id.

    :param lig_id: the id of the Logical Interconnect Group;
    :returns: the Logical Interconnect Group object
    :raise OneViewResourceNotFoundException: If it was not possible
        to retrieve LIG;
    """
    oneview_client = get_oneview_client()
    try:
        return oneview_client.logical_interconnect_groups.get(lig_id)
    except oneview_exceptions.HPOneViewException:
        err_msg = (
            "Could not find a 'Logical Interconnect Group' with the id '%s'"
        ) % lig_id
        LOG.error(err_msg)
        raise exceptions.OneViewResourceNotFoundException(err_msg)


def get_ethernet_network_by_id(oneview_network_id):
    """Get a Ethernet Network Object to a given Network id.

    :param oneview_network_id: the id of the Ethernet Network;
    :returns: the Ethernet Network object;
    :raise OneViewResourceNotFoundException: If it was not possible
        to retrieve the Network;
    """
    oneview_client = get_oneview_client()
    try:
        return oneview_client.ethernet_networks.get(oneview_network_id)
    except oneview_exceptions.HPOneViewException:
        err_msg = (
            "Could not find an 'Ethernet Network' with the id '%s'"
        ) % oneview_network_id
        LOG.error(err_msg)
        raise exceptions.OneViewResourceNotFoundException(err_msg)


def get_uplink_port_group_uris_for_ethernet_network_by_id(oneview_network_id):
    """Get Uplink Port Group URIs for a Ethernet Network by id.

    :param oneview_network_id: the id of the Ethernet Network;
    :returns: a list of Uplink Port Group URIs;
    :raise OneViewResourceNotFoundException: If it was not possible
        to retrieve the list;
    """
    oneview_client = get_oneview_client()
    try:
        return oneview_client.ethernet_networks.get_associated_uplink_groups(
            oneview_network_id)
    except oneview_exceptions.HPOneViewException:
        err_msg = (
            "Could not find an 'Ethernet Network' with the id '%s'"
        ) % oneview_network_id
        LOG.error(err_msg)
        raise exceptions.OneViewResourceNotFoundException(err_msg)


def get_logical_interconnect_group_from_uplink(oneview_client,
                                               uplinkset_id):
    """Get Logical Interconnect Group Object to a given uplinkset id.

    :param oneview_client: a instance of the OneView Client;
    :param uplinkset_id: the id of the Uplinkset;
    :returns: the Logical Interconnect Group object
    """
    uplinkset = oneview_client.uplink_sets.get(uplinkset_id)
    logical_interconnect = oneview_client.logical_interconnects.get(
        uplinkset.get('logicalInterconnectUri'))
    logical_interconnect_group = (
        oneview_client.logical_interconnect_groups.get(
            logical_interconnect.get('logicalInterconnectGroupUri')))

    return logical_interconnect_group


def load_conf_option_to_dict(key_value_option):
    """Convert the uplinkset and flat_net mappings value to a dict.

    It converts the value from the Config fields uplinkset_mappings
    and or flat_net_mappings to a dict object. The object returned
    is in the format:
    {
        provider_from_uplinkset_mapping: ["lig_id", "uplinkset_name"],
        provider_flat_net_mapping: ["oneview_network_id"]
    }

    :param key_value_option: A string with the mappings, in the format
        provider:lig_id:uplinkset_name for uplinkset_mappings, and
        provider:oneview_network_id for flat_net_mappings;
    :returns: the Logical Interconnect Group object
    """
    key_value_dict = {}

    if not key_value_option:
        return key_value_dict

    key_value_list = key_value_option.split(',')

    for key_value in key_value_list:
        values = key_value.split(':')
        provider = values[0]
        key_value_dict.setdefault(provider, []).extend(values[1:])

    return key_value_dict


def network_uri_from_id(network_id):
    return ETHERNET_NETWORK_PREFIX + network_id


def network_dict_for_network_creation(
        physical_network, network_type, neutron_net_id, segmentation_id=None):
    return {
        'provider:physical_network': physical_network,
        'provider:network_type': network_type,
        'provider:segmentation_id': segmentation_id,
        'id': neutron_net_id,
    }


def port_dict_for_port_creation(
        network_id, vnic_type, mac_address, profile, host_id='host_id'):
    return {
        'network_id': network_id,
        'binding:vnic_type': vnic_type,
        'binding:host_id': host_id,
        'mac_address': mac_address,
        'binding:profile': profile
    }


def session_from_context(context):
    """Get the Session from a Neutron Context.

    :param context: a Neutron Context;
    :return: the session;
    """
    plugin_context = getattr(context, '_plugin_context', None)

    return getattr(plugin_context, '_session', None)


def network_from_context(context):
    """Get the Network from a Neutron Context.

    :param context: a Neutron Context;
    :return: the network;
    """
    return getattr(context, '_network', None)


def port_from_context(context):
    """Get the Port from a Neutron Context.

    :param context: a Neutron Context;
    :return: the port;
    """
    return getattr(context, '_port', None)


def local_link_information_from_port(port_dict):
    """Get the Local Link Information from a port.

    :param port_dict: a Neutron port object;
    :return: the local link information;
    """
    binding_profile_dict = port_dict.get('binding:profile')

    return binding_profile_dict.get(
        'local_link_information') if binding_profile_dict else None


def is_local_link_information_valid(local_link_information_list):
    """Verify if a local link information list is valid.

    A local link information list is valid if:
    1 - the list has only one local link information
    2 - It has switch info defined
    3 - The switch info has a server_hardware_id
    4 - The switch info has information about being bootable
    5 - The switch info's bootable value is boolean
    """
    if len(local_link_information_list) != 1:
        return False

    local_link_information = local_link_information_list[0]
    switch_info = local_link_information.get('switch_info')

    if not switch_info:
        return False

    server_hardware_uuid = switch_info.get('server_hardware_id')
    bootable = switch_info.get('bootable')

    if not server_hardware_uuid:
        return False

    return isinstance(bootable, bool)


def server_hardware_from_local_link_information_list(
        oneview_client, local_link_information_list):
    """Get the Server Hardware from Local Link Information.

    :param oneview_client: a instance of the OneView Client;
    :param local_link_information_list: an list of local link information;
    :return: server_hardware;
    """
    switch_info = local_link_information_list[0].get('switch_info')
    if isinstance(switch_info, six.text_type):
        switch_info = jsonutils.loads(switch_info)

    server_hardware_id = switch_info.get('server_hardware_id')
    server_hardware = oneview_client.server_hardware.get(
        server_hardware_id
    )

    return server_hardware


def switch_info_from_local_link_information_list(local_link_information_list):
    """Get the switch_info from Local Link Information.

    :param oneview_client: a instance of the OneView Client;
    :param local_link_information_list: an list of local link information;
    :return: switch_info;
    """
    switch_info = local_link_information_list[0].get('switch_info')
    if isinstance(switch_info, six.text_type):
        switch_info = jsonutils.loads(switch_info)
    return switch_info


def is_rack_server(server_hardware):
    """Verify if Server Hardware is a Rack Server.

    :param server_hardware: a server hardware object;
    :return: True or False;
    """
    return False if server_hardware.get('locationUri') else True


def check_oneview_entities_availability(oneview_client, server_hardware):
    _check_server_hardware_availability(server_hardware)
    _check_server_profile_availability(oneview_client, server_hardware)


def _check_server_hardware_availability(server_hardware):
    max_number_of_attempts = CONF.DEFAULT.retries_to_lock_sh
    interval = CONF.DEFAULT.retries_to_lock_sh_interval

    for _ in range(max_number_of_attempts):
        if not server_hardware.get('powerLock'):
            return True
        time.sleep(interval)
    return False


def _check_server_profile_availability(oneview_client, server_hardware):
    max_number_of_attempts = CONF.DEFAULT.retries_to_lock_sp
    interval = CONF.DEFAULT.retries_to_lock_sp_interval

    for _ in range(max_number_of_attempts):
        if oneview_client.get_server_profile_state(server_hardware):
            return True
        time.sleep(interval)
    return False


def _get_server_profile_state(oneview_client, server_hardware):
    server_profile_dict = server_profile_from_server_hardware(
        oneview_client, server_hardware
    )
    return server_profile_dict.get('status')


def server_profile_from_server_hardware(oneview_client, server_hardware):
    server_profile_uri = server_hardware.get('serverProfileUri')

    if not server_profile_uri:
        LOG.warning("There is no Server Profile available on "
                    "Server Hardware: %s." % server_hardware.get('uuid'))
        return None

    LOG.info("There is Server Profile %s available.", server_profile_uri)
    return oneview_client.server_profiles.get(server_profile_uri)


def get_server_hardware_power_state(server_hardware):
    return server_hardware.get('powerState')


def is_lig_id_uplink_name_mapped(lig_bd_entry, mappings):
    mapped_lig_id = lig_bd_entry.get('oneview_lig_id')
    mapped_uplink_name = lig_bd_entry.get('oneview_uplinkset_name')
    for lig_id, uplinkset_name in zip(mappings[0::2], mappings[1::2]):
        if lig_id == mapped_lig_id and (
                uplinkset_name == mapped_uplink_name):
            return True
    return False


def get_boot_priority(server_profile, bootable):
    if bootable:
        connections = server_profile.get('connections')
        if _is_boot_priority_available(connections, 'Primary'):
            return 'Primary'
        elif _is_boot_priority_available(connections, 'Secondary'):
            return 'Secondary'
        return None
    return 'NotBootable'


def _is_boot_priority_available(connections, boot_priority):
    for connection in connections:
        if connection.get('boot').get('priority') == boot_priority:
            return False
    return True


def port_id_from_mac(server_hardware, mac_address):
    port_info = _get_port_info(server_hardware, mac_address)
    if not port_info:
        return None

    return (
        str(port_info.get('device_slot_location')) + " " +
        str(port_info.get('device_slot_port_number')) + ":" +
        str(port_info.get('physical_port_number')) + "-" +
        str(port_info.get('virtual_port_function'))
    )


def _get_port_info(server_hardware, mac_address):
    port_map = server_hardware.get('portMap')
    device_slots = port_map.get('deviceSlots')
    try:
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
        return None
    except oneview_exceptions.HPOneViewException as ex:
        LOG.warning("Could not get port information on the Server "
                    "Hardware: %s" % server_hardware.get('uuid'))
        raise ex


def connection_with_mac_address(connections, mac_address):
    for connection in connections:
        if connection.get('mac') == mac_address:
            return connection
    return None


def is_port_valid_to_reflect_on_oneview(
        session, port_dict, local_link_information):

    vnic_type = port_dict.get('binding:vnic_type')
    port_id = port_dict.get("id")
    if vnic_type != 'baremetal':
        LOG.warning("'vnic_type' of the port %s must be baremetal" %
                    port_id)
        return False

    network_id = port_dict.get('network_id')
    neutron_oneview_network = database_manager.get_neutron_oneview_network(
        session, network_id
    )
    if not neutron_oneview_network:
        LOG.warning(
            "There is no network created for the port %s" % port_id)
        return False

    return _is_local_link_information_valid(port_id, local_link_information)


def _is_local_link_information_valid(port_id, local_link_information):
    if not local_link_information:
        LOG.warning(
            "The port %s must have 'local_link_information'" % port_id)
        return False

    if len(local_link_information) > 1:
        LOG.warning(
            "'local_link_information' must have only one value")
        return False

    switch_info = switch_info_from_local_link_information_list(
        local_link_information)

    if not switch_info:
        LOG.warning(
            "'local_link_information' must contain 'switch_info'.")
        return False

    server_hardware_id = switch_info.get('server_hardware_id')

    try:
        strutils.bool_from_string(
            subject=switch_info.get('bootable'),
            strict=True)
    except ValueError:
        LOG.warning("'bootable' must be a boolean.")
        return False

    if not server_hardware_id:
        LOG.warning(
            "'local_link_information' must contain `server_hardware_id`.")
        return False

    return True


def remove_inconsistence_from_db(
        session, neutron_network_id, oneview_network_id):
    database_manager.delete_neutron_oneview_network(
        session, neutron_network_id=neutron_network_id
    )
    database_manager.delete_oneview_network_lig(
        session, oneview_network_id=oneview_network_id
    )


def check_valid_resources():
    """Verify if the OneView resources exist.

    Verify if the resources described on the configuration file
    exist on OneView.

    :raise OneViewResourceNotFoundException: If any of the OneView
        resources does not exist.
    :raise ElementNotFoundException: If the UplinkSet name is not
        in the LIG's UplinkSets list. If a Network is not associated
        to any UplinkSet.
    """
    LOG.info("Checking if resources in mappings exist in OneView.")
    check_uplinkset_mappings_resources()
    check_flat_net_mappings_resources()


def check_uplinkset_mappings_resources():
    """Verify if the Logical Interconnect Groups and UplinkSets exist.

    :raise ClientException:: If a Logical Interconnect Group does not exist
        or if a UplinkSet name is not in the LIG's UplinkSets list.
    """
    mappings = load_conf_option_to_dict(CONF.DEFAULT.uplinkset_mappings)

    errors = {"ligs": [], "uplinksets": []}
    for physnet in mappings:
        provider = zip(
            mappings.get(physnet)[0::2],
            mappings.get(physnet)[1::2])

        # Check if Logical Interconnect Groups and UplinkSets exist
        for lig_id, uplinkset_name in provider:
            try:
                lig = get_logical_interconnect_group_by_id(lig_id)
            except exceptions.OneViewResourceNotFoundException:
                errors["ligs"].append(lig_id)
                continue

            uplinksets = lig.get('uplinkSets')

            try:
                get_uplinkset_by_name_from_list(uplinksets, uplinkset_name)
            except exceptions.ElementNotFoundException:
                errors["uplinksets"].append(
                    "%s in the lig %s" % (uplinkset_name, lig_id))

    if errors["ligs"] or errors["uplinksets"]:
        err_msg = (
            'There are invalid values in the UplinkSet mappings '
            'within the OneView configuration file:')
        if errors["ligs"]:
            err_msg += (
                "\nThose Logical Interconnect Groups "
                "could not be found: {err[ligs]}")
        if errors["uplinksets"]:
            err_msg += (
                '\nThose UplinkSets could not be found: {err[uplinksets]}')

        err_msg = err_msg.format(err=errors)
        raise exceptions.ClientException(err_msg)


def check_flat_net_mappings_resources():
    """Verify if the Ethernet Networks exist.

    :raise ClientException: If an Ethernet Network does not exist
        or If there is no UplinkSet associated with the Network.
    """
    mappings = load_conf_option_to_dict(CONF.DEFAULT.flat_net_mappings)

    errors = {"networks": [], "no_uplinkset": []}
    for physnet in mappings:
        oneview_network_ids = mappings.get(physnet)
        for oneview_network_id in oneview_network_ids:
            try:
                get_ethernet_network_by_id(oneview_network_id)
            except exceptions.OneViewResourceNotFoundException:
                errors["networks"].append(oneview_network_id)
                continue

            if not get_uplink_port_group_uris_for_ethernet_network_by_id(
                    oneview_network_id):
                errors["no_uplinkset"].append(oneview_network_id)

    if errors["networks"] or errors["no_uplinkset"]:
        err_msg = (
            'There are invalid values in the Flat net mappings '
            'within the OneView configuration file:')
        if errors["networks"]:
            err_msg += (
                "\nThose Networks could not be found: {err[networks]}")
        if errors["no_uplinkset"]:
            err_msg += (
                '\nThose Networks are not associated '
                'to any Uplinkset: {err[no_uplinkset]}')

        err_msg = err_msg.format(err=errors)
        raise exceptions.ClientException(err_msg)


def uplinkset_mappings_by_type(uplinkset_mappings):
    uplinkset_by_type = {}

    uplinkset_by_type[NETWORK_TYPE_TAGGED] = (
        get_uplinkset_by_type(
            uplinkset_mappings, NETWORK_TYPE_TAGGED
        )
    )

    uplinkset_by_type[NETWORK_TYPE_UNTAGGED] = (
        get_uplinkset_by_type(
            uplinkset_mappings, NETWORK_TYPE_UNTAGGED
        )
    )

    return uplinkset_by_type


def get_uplinkset_by_type(uplinkset_mappings, net_type):
    uplinksets_by_type = {}

    for physnet in uplinkset_mappings:
        provider = uplinkset_mappings.get(physnet)
        for lig_id, uplinkset_name in zip(provider[0::2], provider[1::2]):
            lig = get_logical_interconnect_group_by_id(lig_id)
            lig_uplinksets = lig.get('uplinkSets')

            uplinkset = get_uplinkset_by_name_from_list(
                lig_uplinksets, uplinkset_name
            )
            if uplinkset.get('ethernetNetworkType').lower() == net_type:
                uplinksets_by_type.setdefault(physnet, []).extend(
                    [lig_id, uplinkset_name]
                )
    return uplinksets_by_type


def check_uplinkset_types_constraint(oneview_client, uplinkset_mappings):
    """Check the number of uplinkset types for a provider in a LIG.

    It is only possible to map one provider to at the most one uplink
    of each type.
    """
    LOG.info("Checking if a provider has two mappings for the same LIG with "
             "different uplinksets of the same type.")
    for provider in uplinkset_mappings:
        provider_mapping = zip(
            uplinkset_mappings.get(provider)[::2],
            uplinkset_mappings.get(provider)[1::2])
        uplinksets_type = {}
        for lig_id, ups_name in provider_mapping:
            lig_mappings = uplinksets_type.setdefault(lig_id, [])
            lig = oneview_client.logical_interconnect_groups.get(
                lig_id
            )
            uplinkset = get_uplinkset_by_name_from_list(
                lig.get('uplinkSets'), ups_name)
            lig_mappings.append(uplinkset.get('ethernetNetworkType'))

            if len(lig_mappings) != len(set(lig_mappings)):
                err = (
                    "The provider %(provider)s has more than one "
                    "uplinkset of the same type in the logical "
                    "interconnect group %(lig_id)s."
                ) % {"provider": provider, "lig_id": lig_id}
                LOG.error(err)
                raise Exception(err)


def check_unique_lig_per_provider_constraint(uplinkset_mappings):
    LOG.info("Checking if different providers have the same mapping.")
    for provider in uplinkset_mappings:
        for provider2 in uplinkset_mappings:
            if provider != provider2:
                provider_lig_mapping_tupples = zip(
                    uplinkset_mappings.get(provider)[::2],
                    uplinkset_mappings.get(provider)[1::2])
                provider2_lig_mapping_tupples = zip(
                    uplinkset_mappings.get(provider2)[::2],
                    uplinkset_mappings.get(provider2)[1::2])
                identical_mappings = (set(provider_lig_mapping_tupples) &
                                      set(provider2_lig_mapping_tupples))
                if identical_mappings:
                    err_message_attrs = {
                        "prov1": provider,
                        "prov2": provider2,
                        "identical_mappings": "\n".join(
                            (", ".join(mapping)
                             for mapping in identical_mappings)
                        )
                    }
                    err = (
                        "The providers %(prov1)s and %(prov2)s are being "
                        "mapped to the same Logical Interconnect Group "
                        "and the same Uplinkset.\n"
                        "The LIG ids and Uplink names are: "
                        "%(identical_mappings)s"
                    ) % err_message_attrs
                    LOG.error(err)
                    raise Exception(err)


def delete_outdated_flat_mapped_networks(flat_net_mappings):
    LOG.info("Synchronizing flat network mappings.")
    session = get_database_session()
    mappings = flat_net_mappings.values()
    mapped_networks_uuids = list(chain.from_iterable(mappings))
    oneview_networks_uuids = (
        network.oneview_network_id for network
        in database_manager.list_neutron_oneview_network(session)
        if not network.manageable)
    unmapped_networks_uuids = (
        uuid for uuid
        in oneview_networks_uuids
        if uuid not in mapped_networks_uuids)
    for uuid in unmapped_networks_uuids:
        database_manager.delete_neutron_oneview_network(
            session, oneview_network_id=uuid)


def get_database_session():
    connection = CONF.database.connection
    Session = sessionmaker(bind=create_engine(connection),
                           autocommit=True)
    return Session()
