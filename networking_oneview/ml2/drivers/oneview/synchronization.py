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

from datetime import datetime

from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager

from oslo_service import loopingcall

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_session(connection):
    Session = sessionmaker(bind=create_engine(connection), autocommit=True)
    return Session()


class Synchronization:
    def __init__(self, neutron_oneview_client, connection):
        self.neutron_oneview_client = neutron_oneview_client
        self.connection = connection
        # self.synchronize_neutron_networks_from_neutron()
        self.delete_oneview_networks_unmapped()

    def synchronize_neutron_networks_from_neutron(self):
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        start_time = datetime.now()
        print start_time

        session = get_session(self.connection)
        for network, network_segment in (
            db_manager.list_networks_and_segments_with_physnet(session)
        ):
            id = network.get('id')
            physical_network = network_segment.get('physical_network')
            network_type = network_segment.get('network_type')
            segmentation_id = network_segment.get('segmentation_id')
            print segmentation_id
            network_dict = common.network_dict_for_network_creation(
                physical_network, network_type, id, segmentation_id
            )
            print network_dict
            self.neutron_oneview_client.network.create(session, network_dict)

            print network
            print network_segment
            print
            print
        now = datetime.now()
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        print now
        print now - start_time
        import time
        time.sleep(5)

    def delete_oneview_networks_unmapped(self):
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        start_time = datetime.now()
        print start_time

        session = get_session(self.connection)

        for network in self.oneview_client.ethernet_networks.get_all():
            m = re.search('Neutron\[(.*)\]', network.get('name'))
            if m:
                oneview_network_id = common.id_from_uri(network.get('uri'))
                neutron_network_id = m.group(1)

                neutron_network = db_manager.get_neutron_network(
                    session, neutron_network_id
                )
                if neutron_network is None:
                    self.oneview_client.ethernet_networks.delete(
                        oneview_network_id
                    )
                    neutron_oneview_network = (
                        db_manager.get_neutron_oneview_network(
                            session, neutron_network_id
                        )
                    )

                if neutron_oneview_net is None:

        for network, network_segment in (
            db_manager.list_networks_and_segments_with_physnet(session)
        ):
            id = network.get('id')
            physical_network = network_segment.get('physical_network')
            network_type = network_segment.get('network_type')
            segmentation_id = network_segment.get('segmentation_id')
            print segmentation_id
            network_dict = common.network_dict_for_network_creation(
                physical_network, network_type, id, segmentation_id
            )
            print network_dict
            self.neutron_oneview_client.network.create(session, network_dict)
            print network
            print network_segment
            print
            print
        now = datetime.now()
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        print "==============================================================="
        print now
        print now - start_time
        import time
        time.sleep(5)
