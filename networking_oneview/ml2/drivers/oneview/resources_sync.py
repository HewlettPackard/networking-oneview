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

from neutron._i18n import _LI
from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from oneview_client import utils
from oslo_log import log
from oslo_service import loopingcall
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


LOG = log.getLogger(__name__)


class ResourcesSyncService(object):
    def __init__(self, oneview_client, connection):
        self.oneview_client = oneview_client
        Session = sessionmaker(bind=create_engine(connection))
        self.session = Session()

    def start(self, interval):
        heartbeat = loopingcall.FixedIntervalLoopingCall(self.task)
        heartbeat.start(interval=interval, initial_delay=interval)

    def task(self):
        LOG.info(_LI("Starting periodic task"))
        self.sync_oneview_and_db()

    def sync_oneview_and_db(self):
        def get_oneview_network_uuid(uuid):
            try:
                return self.oneview_client.ethernet_network.get(uuid)
            except Exception:
                return None

        for neutron_oneview_network in db_manager.list_neutron_oneview_network(
            self.session
        ):
            oneview_network = get_oneview_network_uuid(
                neutron_oneview_network.oneview_network_uuid
            )
            neutron_network = db_manager.get_neutron_network(
                self.session, neutron_oneview_network.neutron_network_uuid
            )

            if neutron_network is None and oneview_network is None:
                self.delete_network_from_db(neutron_oneview_network)
            elif neutron_network is None:
                self.delete_network_from_oneview_and_db(
                    neutron_oneview_network
                )
            elif oneview_network is None:
                self.create_network_in_oneview(neutron_oneview_network)

    def delete_network_from_db(self, neutron_oneview_network):
        db_manager.delete_neutron_oneview_network(
            self.session, neutron_oneview_network.neutron_network_uuid
        )
        self.session.commit()

    def delete_network_from_oneview_and_db(self, neutron_oneview_network):
        db_manager.delete_neutron_oneview_network(
            self.session, neutron_oneview_network.neutron_network_uuid
        )
        self.session.commit()
        self.oneview_client.ethernet_network.delete(
            neutron_oneview_network.oneview_network_uuid
        )

    def create_network_in_oneview(self, neutron_oneview_network):
        uuid = neutron_oneview_network.neutron_network_uuid
        neutron_network = db_manager.get_neutron_network(self.session, uuid)
        network_segment = db_manager.get_network_segment(self.session, uuid)

        kwargs = common.prepare_oneview_network_args(
            neutron_network.name, network_segment.segmentation_id
        )
        oneview_network_uri = self.oneview_client.ethernet_network.create(
            **kwargs
        )
        oneview_network_uuid = utils.get_uuid_from_uri(oneview_network_uri)
        neutron_oneview_network.oneview_network_uuid = oneview_network_uuid

        self.session.commit()
