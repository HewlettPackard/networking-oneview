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
        switch_info_dict = local_link_information.get('switch_info')
        if switch_info_dict:
            return switch_info_dict.get('boot_priority')


def server_hardware_from_local_link_information(local_link_information):
    if local_link_information:
        switch_info_dict = local_link_information.get('switch_info')
        if switch_info_dict:
            return switch_info_dict.get('server_hardware_uuid')
