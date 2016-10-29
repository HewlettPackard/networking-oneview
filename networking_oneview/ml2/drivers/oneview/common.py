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

ETHERNET_NETWORK_PREFIX = '/rest/ethernet-networks/'


# Utils
def id_from_uri(uri):
    if uri:
        return uri.split("/")[-1]


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


def network_uri_from_id(network_id):
    return ETHERNET_NETWORK_PREFIX + network_id


# Context
def session_from_context(context):
    if context is None:
        return None

    plugin_context = context._plugin_context
    if plugin_context is None:
        return None

    return plugin_context._session


def network_from_context(context):
    if context is None:
        return None

    return context._network


def port_from_context(context):
    if context is None:
        return None

    return context._port


def local_link_information_from_port(port_dict):
    binding_profile_dict = port_dict.get('binding:profile')
    if binding_profile_dict is None:
        return None
    return binding_profile_dict.get('local_link_information')


def is_local_link_information_valid(local_link_information_list):
    if len(local_link_information_list) != 1:
        return False
    local_link_information = local_link_information_list[0]
    switch_info = local_link_information.get('switch_info')
    if switch_info is None:
        return False

    server_hardware_uuid = switch_info.get('server_hardware_id')
    bootable = switch_info.get('bootable')

    if server_hardware_uuid is None or bootable is None:
        return False

    return type(bootable) == bool
