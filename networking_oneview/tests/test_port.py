from neutronclient.v2_0 import client
from neutron.plugins.ml2.drivers.oneview import mech_oneview
from neutron.plugins.ml2.drivers.oneview import neutron_oneview_client
from hpOneView.oneview_client import OneViewClient
import time


server_hardware_id = "37333036-3831-4753-4831-31315838524E"

user = 'admin'
passwd = 'password'
tenant = 'admin'
auth = 'http://10.4.4.143:5000/v2.0'
user_hp = 'administrator'
pass_hp = 'r00t@0n3v13w'
ip_hp = '10.5.0.33'
oneview_client = OneViewClient({
    "ip": ip_hp,
    "credentials": {
        "userName": user_hp,
        "password": pass_hp
    }
})
params = {
    'username': user,
    'password': passwd,
    'tenant_name': tenant,
    'auth_url': auth
}

n_client = neutron_oneview_client.Client(
    oneview_client
)

q_client = client.Client(**params)


def test_create_port_with_machine_on():
    n_client.port.update_server_hardware_power_state(server_hardware_id, "On")
    assert n_client.port.get_server_hardware_power_state(
        server_hardware_id) == 'On', "Machine is on."
    port_ = q_client.create_port(body_with_lli)
    p_id = port_.get('port').get('id')
    print port_
    q_client.delete_port(p_id)
    print p_id
    assert n_client.port.get_server_hardware_power_state(
        server_hardware_id) == 'On', "Machine is on."


def test_create_port_with_machine_off():
    n_client.port.update_server_hardware_power_state(server_hardware_id, "Off")
    assert n_client.port.get_server_hardware_power_state(
        server_hardware_id) == 'Off', "Machine is off."
    port_ = q_client.create_port(body_with_lli)
    p_id = port_.get('port').get('id')
    print port_
    q_client.delete_port(p_id)
    print p_id
    assert n_client.port.get_server_hardware_power_state(
        server_hardware_id) == 'Off', "Machine is off."


def create_and_delete_port(q_client, create_body):
    print "Creating Port..."
    p = q_client.create_port(create_body)
    print p
    p_id = p.get('port').get('id')
    q_client.delete_port(p_id)
    print p_id
    q_client.delete_port(p_id)
    print p.get('port')


# def create_update_and_delete_port(q_client, create_body, update_body):
#     # print "Creating Port..."
#     # p = q_client.create_port(create_body)
#     # p_id = p.get('port').get('id')
#     # raw_input("aperte para update")
#     try:
#         print "Updating Port..."
#         q_client.update_port(p_id, update_body)
#         p = p.get('port')
#         print p
#     # finally:
#     #     raw_input("aperte para delete")
#     #     print "Deleting Port..."
#     #     q_client.delete_port(p_id)


def update_port(q_client, p_id, update_body):
    print "Updating Port..."
    q_client.update_port(p_id, update_body)


net_id = '327913b8-6a02-4514-b2a2-3b971db4474a'
mac = '02:23:13:25:23:04'
different_mac = '02:23:13:25:23:00'
server_hardware_uuid = '37333036-3831-4753-4831-31315838524E'
p_id = '2052aa08-dc20-4976-ac06-5b7eac6fdc90'

binding_profile = {
    'local_link_information': [
        {
            'switch_info': {
                'server_hardware_uuid': server_hardware_uuid,
                'bootable': True
            },
            'port_id':'ovs-node-0',
            'switch_id':'16:6c:13:c2:03:48'
        }
    ],
}

binding_profile_with_different_boot_priority = {
    'local_link_information': [
        {
            'switch_info': {
                'server_hardware_uuid': server_hardware_uuid,
                'boot_priority': 'NotBootable'
            },
            'port_id': 'ovs-node-0',
            'switch_id': '16:6c:13:c2:03:48'
        }
    ],
}


body = {
    'port': {
        'network_id': net_id,
        'admin_state_up': True,
        'binding:vnic_type': 'baremetal',
        'device_owner': 'baremetal:none',
        'mac_address': mac
    }
}

body_with_lli = {
    'port': {
        'network_id': net_id,
        'admin_state_up': True,
        'binding:vnic_type': 'baremetal',
        'device_owner': 'baremetal:none',
        'binding:profile': binding_profile,
        'mac_address': mac
    }
}

update_body = {
    'port': {
        'admin_state_up': True,
        'binding:vnic_type': 'baremetal',
        'device_owner': 'baremetal:none',
        'binding:profile': None,
        'mac_address': mac
    }
}

update_body_with_lli = {
    'port': {
        'admin_state_up': True,
        'binding:vnic_type': 'baremetal',
        'device_owner': 'baremetal:none',
        'binding:profile': binding_profile,
        'mac_address': mac
    }
}


update_body_different_mac = {
    'port': {
        'admin_state_up': True,
        'binding:vnic_type': 'baremetal',
        'device_owner': 'baremetal:none',
        'binding:profile': binding_profile,
        'mac_address': different_mac
    }
}

update_body_with_different_boot_priority = {
    'port': {
        'admin_state_up': True,
        'binding:vnic_type': 'baremetal',
        'device_owner': 'baremetal:none',
        'binding:profile': binding_profile_with_different_boot_priority,
        'mac_address': mac
    }
}

# Case 1
test_create_port_with_machine_on()

# Case 2
test_create_port_with_machine_off()
