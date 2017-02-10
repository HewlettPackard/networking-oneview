import json

from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker

from neutron.db.model_base import BASEV2
from networking_oneview.db.oneview_network_db import NeutronOneviewNetwork
from networking_oneview.db.oneview_network_db import OneviewNetworkUplinkset
from networking_oneview.db.oneview_network_db import (
    OneviewLogicalInterconnectGroup
    )


def create_tables(connection):
    engine = create_engine(connection)
    BASEV2.metadata.create_all(engine)


def drop_tables(connection):
    engine = create_engine(connection)
    BASEV2.metadata.drop_all(engine)

if __name__ == '__main__':
    connection = 'mysql+pymysql://root:password@127.0.0.1/neutron?charset=utf8'
    create_tables(connection)
