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
from neutron.db import oneview_network_db
from neutron.db.segments_db import NetworkSegment


# Neutron Network
def get_neutron_network(session, uuid):
    with session.begin(subtransactions=True):
        return session.query(
            Network
        ).filter_by(
            id=uuid
        ).first()


# Neutron Network Segments
def get_network_segment(session, network_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            NetworkSegment
        ).filter_by(
            network_id=network_uuid
        ).first()


# Neutron OneView Network
def list_neutron_oneview_network(session):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).all()


def insert_neutron_oneview_network(
    session, neutron_network_uuid, oneview_network_uuid
):
    with session.begin(subtransactions=True):
        net = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_uuid, oneview_network_uuid
        )
        session.add(net)


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


def delete_neutron_oneview_network(session, neutron_network_uuid):
    with session.begin(subtransactions=True):
        session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).filter_by(
            neutron_network_uuid=neutron_network_uuid
        ).delete()


# OneView Network Uplinkset
def insert_oneview_network_uplinkset(
    session, oneview_network_uuid, uplinkset_uuid
):
    with session.begin(subtransactions=True):
        net = oneview_network_db.OneviewNetworkUplinkset(
            oneview_network_uuid, uplinkset_uuid
        )
        session.add(net)


def delete_oneview_network_uplinkset(
    session, oneview_network_uuid, oneview_uplinkset_uuid
):
    with session.begin(subtransactions=True):
        session.query(
            oneview_network_db.OneviewNetworkUplinkset
        ).filter_by(
            oneview_network_uuid=oneview_network_uuid,
            oneview_uplinkset_uuid=oneview_uplinkset_uuid
        ).delete()


def get_oneview_network_uplinkset(session, neutron_network_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewNetwork
        ).filter_by(
            neutron_network_uuid=neutron_network_uuid
        ).all()


# Neutron OneView Port
def insert_neutron_oneview_port(
    session, neutron_port_uuid, oneview_server_profile_uuid,
    oneview_connection_id
):
    with session.begin(subtransactions=True):
        port = oneview_network_db.NeutronOneviewPort(
            neutron_port_uuid, oneview_server_profile_uuid,
            oneview_connection_id
        )
        session.add(port)


def delete_neutron_oneview_port(session, neutron_port_uuid):
    with session.begin(subtransactions=True):
        session.query(
            oneview_network_db.NeutronOneviewPort
        ).filter_by(
            neutron_port_uuid=neutron_port_uuid
        ).delete()


def get_neutron_oneview_port(session, neutron_port_uuid):
    with session.begin(subtransactions=True):
        return session.query(
            oneview_network_db.NeutronOneviewPort
        ).filter_by(
            neutron_port_uuid=neutron_port_uuid
        ).first()
