import sqlalchemy as sa
from neutron.db import model_base


class NeutronOneviewNetwork(model_base.BASEV2):
    __tablename__ = 'neutron_oneview_network'
    neutron_network_uuid = sa.Column(sa.String(36), primary_key=True)
    oneview_network_uuid = sa.Column(sa.String(36), nullable=False)

    def __init__(self, neutron_network_uuid, oneview_network_uuid):
        self.neutron_network_uuid = neutron_network_uuid
        self.oneview_network_uuid = oneview_network_uuid


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
