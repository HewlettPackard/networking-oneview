
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from oneview_client import exceptions
from oslo_log import log
from oslo_service import loopingcall
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


LOG = log.getLogger(__name__)


class ResourcesSyncService:
    def __init__(self, oneview_client, connection):
        self.oneview_client = oneview_client
        Session = sessionmaker(bind=create_engine(connection))
        self.session = Session()

    def start(self, interval):
        heartbeat = loopingcall.FixedIntervalLoopingCall(self.task)
        heartbeat.start(interval=interval, initial_delay=interval)

    def _delete_networks_from_tables(
        self, neutron_network_uuid, oneview_network_uuid
    ):
        db_manager.delete_neutron_oneview_network(
            self.session, neutron_network_uuid
        )
        db_manager.delete_oneview_network_uplinkset(
            self.session, oneview_network_uuid
        )
        self.session.commit()

    def task(self):
        LOG.info("Starting periodic task")
        neutron_oneview_network_list = db_manager.list_neutron_oneview_network(
            self.session
        )
        print "###############################################################"
        print "###############################################################"
        print "###############################################################"
        print "###############################################################"
        print "###############################################################"
        for neutron_oneview_network in neutron_oneview_network_list:
            neutron_network_uuid = neutron_oneview_network.neutron_network_uuid
            oneview_network_uuid = neutron_oneview_network.oneview_network_uuid
            print neutron_network_uuid
            print oneview_network_uuid

            try:
                oneview_network = self.oneview_client.ethernet_network.get(
                    oneview_network_uuid
                )
            except exceptions.OneViewResourceNotFoundError:
                msg = "Database inconsistent. OneView Network: " +\
                    "%(oneview_network_uuid)s not found." % (
                        {"oneview_network_uuid": oneview_network_uuid}
                    )
                LOG.warning(msg)

                neutron_network = db_manager.get_neutron_network(
                    self.session, neutron_network_uuid
                )
                msg = "Database inconsistent. Neutron Network: " +\
                    "%(neutron_network_uuid)s not found." % (
                        {"neutron_network_uuid": neutron_network_uuid}
                    )
                LOG.warning(msg)

                self._delete_networks_from_tables(
                    neutron_network_uuid, oneview_network_uuid
                )

            print oneview_network
