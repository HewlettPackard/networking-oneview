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
import six

from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import importutils

from hpOneView import exceptions
from hpOneView.exceptions import HPOneViewException
from hpOneView.oneview_client import OneViewClient

from networking_oneview.conf import CONF

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
        raise exceptions.HPOneViewException(
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
        except HPOneViewException:
            LOG.debug("Reauthenticating to OneView.")
            oneview_conf = get_oneview_conf()
            self.oneview_client.connection.login(oneview_conf["credentials"])
        return f(self, *args, **kwargs)
    return wrapper


# Utils
def id_from_uri(uri):
    if uri:
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
    :raise Exception: Uplinkset name not found in Uplinkset list;
    """
    try:
        uplinkset_obj = next(
            uplinkset for uplinkset in uplinkset_list if uplinkset.get(
                'name') == uplinkset_name)
    except Exception:
        err_msg = "Uplinkset not found in Uplinkset List"
        LOG.error(err_msg)
        raise Exception(err_msg)

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


def get_logical_interconnect_group_by_id(oneview_client, lig_id):
    """Get a Logical Interconnect Group Object to a given LIG id.

    :param oneview_client: a instance of the OneView Client;
    :param lig_id: the id of the Logical Interconnect Group;
    :returns: the Logical Interconnect Group object
    :raise HPOneViewException: If was not possible to retrieve LIG;
    """
    try:
        return oneview_client.logical_interconnect_groups.get(lig_id)
    except exceptions.HPOneViewException as err:
        LOG.error(err)
        raise err


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
    physical_network, network_type, neutron_net_id, segmentation_id=None
):
    return {
        'provider:physical_network': physical_network,
        'provider:network_type': network_type,
        'provider:segmentation_id': segmentation_id,
        'id': neutron_net_id,
    }


def port_dict_for_port_creation(
    network_id, vnic_type, mac_address, profile, host_id='host_id'
):
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
