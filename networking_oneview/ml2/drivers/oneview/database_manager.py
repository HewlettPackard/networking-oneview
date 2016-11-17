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

from neutron.db.models_v2 import Network
from neutron.db.models_v2 import Port
from neutron.db import oneview_network_db
from neutron.db.segments_db import NetworkSegment
from neutron.plugins.ml2.models import PortBinding
from sqlalchemy import event


# Neutron Network
def get_neutron_network(session, id):
    with session.begin(subtransactions=True):
        return session.query(
            Network
        ).filter_by(
            id=id
        ).first()


def list_neutron_networks(session):
    with session.begin(subtransactions=True):
        return session.query(Network).all()


def list_networks_and_segments_with_physnet(session):
    with session.begin(subtransactions=True):
        return session.query(
            Network, NetworkSegment
        ).filter(
            Network.id == NetworkSegment.network_id,
            NetworkSegment.physical_network.isnot(None)
        ).all()


def get_neutron_network_with_segment(session, id):
    with session.begin(subtransactions=True):
        return session.query(
            Network, NetworkSegment
        ).filter(
            Network.id == id,
            Network.id == NetworkSegment.network_id
        ).first()


def get_management_neutron_network(session, network_id):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).filter_by(
            neutron_network_uuid=network_id,
        ).first()


# Neutron Network Segments
def get_network_segment(session, network_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            NetworkSegment
        ).filter_by(
            network_id=network_uuid
        ).first()


# Neutron Ports
def get_port_by_mac_address(session, mac_address):
    with session.begin(subtransactions=True):
        return session.query(
            Port
        ).filter_by(
            mac_address=mac_address
        ).first()


def list_port_with_network(session, network_id):
    with session.begin(subtransactions=True):
        return session.query(
            Port
        ).filter(
            Port.network_id == network_id
        ).all()


def get_port_with_binding_profile(session, network_id):
    with session.begin(subtransactions=True):
        return session.query(
            Port, PortBinding
        ).filter(
            Port.network_id == network_id,
            Port.id == PortBinding.port_id,
            PortBinding.profile.isnot(None),
            PortBinding.profile != ''
        ).all()


# OneView Network Uplinkset
def list_oneview_network_uplinkset(session):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.OneviewNetworkUplinkset
        ).all()


# Neutron OneView Network
def list_neutron_oneview_network(session):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).all()


def list_neutron_oneview_network_manageable(session):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).filter_by(
            manageable=False
        ).all()


def insert_neutron_oneview_network(
    session, neutron_network_uuid, oneview_network_uuid,
    commit, manageable=True
):
    # commit variable is used temporarily
    # commit is True when the call insert comes from init_sync.py
    # commit is False when the call insert comes from mech_oneview.py
    # TODO

    with session.begin(subtransactions=True):
        net = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_uuid, oneview_network_uuid, manageable
        )
        session.add(net)
    if commit:
        session.commit()


def update_neutron_oneview_network(session, neutron_uuid, new_oneview_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).all()


def get_neutron_oneview_network(session, neutron_network_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).filter_by(
            neutron_network_uuid=neutron_network_uuid
        ).first()


def delete_neutron_oneview_network(
    session, neutron_network_uuid, commit=False
):
    with session.begin(subtransactions=True):
        session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).filter_by(
            neutron_network_uuid=neutron_network_uuid
        ).delete()
    if commit:
        session.commit()


# OneView Network Uplinkset
def get_oneview_network_uplinkset(session, network_id, uplinkset_id):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.OneviewNetworkUplinkset
        ).filter_by(
            oneview_uplinkset_uuid=uplinkset_id,
            oneview_network_uuid=network_id
        ).first()


def insert_oneview_network_uplinkset(
    session, oneview_network_uuid, uplinkset_uuid, commit=False
):
    with session.begin(subtransactions=True):
        net = oneview_network_db.OneviewNetworkUplinkset(
            oneview_network_uuid, uplinkset_uuid
        )
        session.add(net)
    if commit:
        session.commit()


def delete_oneview_network_uplinkset(
    session, uplinkset_id, network_id, commit=False
):
    with session.begin(subtransactions=True):
        session.query(
            oneview_network_db.OneviewNetworkUplinkset
        ).filter_by(
            oneview_uplinkset_uuid=uplinkset_id,
            oneview_network_uuid=network_id
        ).delete()
    if commit:
        session.commit()


def delete_oneview_network_uplinkset_by_network(
    session, network_id, commit=False
):
    with session.begin(subtransactions=True):
        session.query(
            oneview_network_db.OneviewNetworkUplinkset
        ).filter_by(
            oneview_network_uuid=network_id
        ).delete()
    if commit:
        session.commit()


def get_network_uplinksets(session, oneview_network_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.OneviewNetworkUplinkset
        ).filter_by(
            oneview_network_uuid=oneview_network_uuid
        ).all()


def get_ml2_port_binding(session, neutron_port_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            PortBinding
        ).filter_by(
            port_id=neutron_port_uuid
        ).first()
