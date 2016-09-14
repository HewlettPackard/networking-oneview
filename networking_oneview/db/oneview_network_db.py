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

from neutron.db import model_base
import sqlalchemy as sa


class NeutronOneviewNetwork(model_base.BASEV2):
    __tablename__ = 'neutron_oneview_network'
    neutron_network_uuid = sa.Column(sa.String(36), primary_key=True)
    oneview_network_uuid = sa.Column(sa.String(36), nullable=False)
    manageable = sa.Column(sa.Boolean)

    def __init__(
        self, neutron_network_uuid, oneview_network_uuid, manageable=True
    ):
        self.neutron_network_uuid = neutron_network_uuid
        self.oneview_network_uuid = oneview_network_uuid
        self.manageable = manageable


class OneviewNetworkUplinkset(model_base.BASEV2):
    __tablename__ = 'oneview_network_uplinkset'
    oneview_network_uuid = sa.Column(sa.String(36), primary_key=True)
    oneview_uplinkset_uuid = sa.Column(sa.String(36), primary_key=True)

    def __init__(self, oneview_network_uuid, oneview_uplinkset_uuid):
        self.oneview_network_uuid = oneview_network_uuid
        self.oneview_uplinkset_uuid = oneview_uplinkset_uuid


class NeutronOneviewPort(model_base.BASEV2):
    __tablename__ = 'neutron_oneview_port'
    neutron_port_uuid = sa.Column(sa.String(36), primary_key=True)
    oneview_server_profile_uuid = sa.Column(sa.String(36), primary_key=False)
    oneview_connection_id = sa.Column(sa.String(36), primary_key=False)

    def __init__(
        self, neutron_port_uuid, oneview_server_profile_uuid,
        oneview_connection_id
    ):
        self.neutron_port_uuid = neutron_port_uuid
        self.oneview_server_profile_uuid = oneview_server_profile_uuid
        self.oneview_connection_id = oneview_connection_id
