import json

from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker

from neutron.db.model_base import BASEV2
#from neutron.db.models_v2 import Network
#from neutron.db.models_v2 import Port
from networking_oneview.db.oneview_network_db import NeutronOneviewNetwork
from networking_oneview.db.oneview_network_db import OneviewNetworkUplinkset
#from neutron.db.segments_db import NetworkSegment
#from neutron.db.qos import models
#from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
#from neutron.plugins.ml2.models import PortBinding


def create_tables(connection):
    engine = create_engine(connection)
    BASEV2.metadata.create_all(engine)


def drop_tables(connection):
    engine = create_engine(connection)
    BASEV2.metadata.drop_all(engine)

if __name__ == '__main__':
    connection = 'mysql+pymysql://root:stackdb@127.0.0.1/neutron?charset=utf8'
    #drop_tables(connection)
    create_tables(connection)

