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

import json


def load_oneview_network_mapping_conf_to_dict(oneview_network_mapping):
    oneview_network_mapping_dict = {}
    if oneview_network_mapping is None or not oneview_network_mapping:
        return oneview_network_mapping_dict

    oneview_network_mapping_list = oneview_network_mapping.split(',')

    for neutron_oneview in oneview_network_mapping_list:
        neutron_net_name, oneview_net_id = neutron_oneview.split(':')
        oneview_network_mapping_dict[neutron_net_name] = oneview_net_id

    return oneview_network_mapping_dict


def load_conf_option_to_dict(key_value_option):
    key_value_dict = {}
    if key_value_option is None or not key_value_option:
        return key_value_dict
    key_value_list = key_value_option.split(',')

    for key_value in key_value_list:
        key, value = key_value.split(':')
        if key_value_dict.get(key) is None:
            key_value_dict[key] = []
        key_value_dict[key].append(value)

    return key_value_dict


def get_network_from_port_context(context):
    network_context_dict = context._network_context
    if network_context_dict is None:
        return None
    return network_context_dict._network


def get_vnic_type_from_port_context(context):
    port_context_json = context._port
    if port_context_json is None:
        return None
    return port_context_json.get('binding:vnic_type')


def local_link_information_from_context(port_context):
    if port_context is None:
        return None
    binding_profile_dict = port_context.get('binding:profile')
    if binding_profile_dict is None:
        return None
    return binding_profile_dict.get('local_link_information')


def first_local_link_information_from_port_context(port_context):
    lli_list = local_link_information_from_context(port_context)
    if lli_list is None or len(lli_list) == 0:
        return None
    elif len(lli_list) > 1:
        raise ValueError(
            "'local_link_information' must have only one value"
        )

    return lli_list[0]


def boot_priority_from_local_link_information(local_link_information):
    if local_link_information:
        switch_info_string = local_link_information.get('switch_info')
        if switch_info_string:
            switch_info_string = switch_info_string.replace("'", '"')
            switch_info_dict = json.loads(switch_info_string)
            return switch_info_dict.get('boot_priority')


def server_hardware_from_local_link_information(local_link_information):
    if local_link_information:
        switch_info_string = local_link_information.get('switch_info')
        if switch_info_string:
            switch_info_string = switch_info_string.replace("'", '"')
            switch_info_dict = json.loads(switch_info_string)
            return switch_info_dict.get('server_hardware_uuid')


def id_from_uri(uri):
    if uri:
        return uri.split("/")[-1]
