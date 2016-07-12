
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from oslo_service import loopingcall
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class ResourcesSyncService:
    def __init__(self, connection):
        Session = sessionmaker(bind=create_engine(connection))
        self.session = session
        self.start()

    def start(self):
        heartbeat = loopingcall.FixedIntervalLoopingCall(self.task)
        heartbeat.start(interval=4, initial_delay=4)

    def task(self):
        print "###############################################################"
        print "###############################################################"
        print "###############################################################"
        print "###############################################################"
        print "###############################################################"
        print "TASK",
        print db_manager.list_neutron_oneview_network(self.session)
