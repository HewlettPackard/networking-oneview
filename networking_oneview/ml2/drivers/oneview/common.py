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

from hpOneView import exceptions
from oslo_log import log

MAPPING_TYPE_NONE = 0
FLAT_NET_MAPPINGS_TYPE = 1
UPLINKSET_MAPPINGS_TYPE = 2

NETWORK_TYPE_TAGGED = 'tagged'
NETWORK_TYPE_UNTAGGED = 'untagged'
ETHERNET_NETWORK_PREFIX = '/rest/ethernet-networks/'

LOG = log.getLogger(__name__)


# Utils
def id_from_uri(uri):
    if uri:
        return uri.split("/")[-1]


def id_list_from_uri_list(uri_list):
    return [id_from_uri(uri) for uri in uri_list]


def uplinksets_id_from_network_uplinkset_list(net_uplink_list):
    return [net_uplink.oneview_uplinkset_id for net_uplink in net_uplink_list]


def get_uplinkset_by_name_from_list(uplinkset_list, uplinkset_name):
    try:
        uplinkset_obj = (
            uplinkset for uplinkset in uplinkset_list if uplinkset.get(
                'name') == uplinkset_name).next()
    except Exception:
        LOG.error("Uplinkset not found in Logical Interconnect Group")
        raise

    return uplinkset_obj


def get_logical_interconnect_group_by_id(self, oneview_client, lig_id):
    try:
        return oneview_client.logical_interconnect_groups.get(lig_id)
    except exceptions.HPOneViewException as err:
        LOG.error(err)
        raise err


def load_conf_option_to_dict(key_value_option):
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
    physical_network, network_type, id, segmentation_id=None
):
    return {
        'provider:physical_network': physical_network,
        'provider:network_type': network_type,
        'provider:segmentation_id': segmentation_id,
        'id': id,
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


# Context
def session_from_context(context):
    plugin_context = getattr(context, '_plugin_context', None)

    return getattr(plugin_context, '_session', None)


def network_from_context(context):
    return getattr(context, '_network', None)


def port_from_context(context):
    return getattr(context, '_port', None)


def local_link_information_from_port(port_dict):
    binding_profile_dict = port_dict.get('binding:profile')

    return binding_profile_dict.get(
        'local_link_information') if binding_profile_dict else None


def is_local_link_information_valid(local_link_information_list):
    if len(local_link_information_list) != 1:
        return False

    local_link_information = local_link_information_list[0]
    switch_info = local_link_information.get('switch_info')

    if not switch_info:
        return False

    server_hardware_uuid = switch_info.get('server_hardware_id')
    bootable = switch_info.get('bootable')

    if not server_hardware_uuid or not bootable:
        return False

    return type(bootable) == bool
