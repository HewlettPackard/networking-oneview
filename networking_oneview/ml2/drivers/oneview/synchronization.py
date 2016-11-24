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

import re

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
    def __init__(self, oneview_client, neutron_oneview_client, connection):
        self.oneview_client = oneview_client
        self.neutron_oneview_client = neutron_oneview_client
        self.connection = connection

        heartbeat = loopingcall.FixedIntervalLoopingCall(self.synchronize)
        heartbeat.start(interval=3600, initial_delay=0)

    def synchronize(self):
        self.create_oneview_networks_from_neutron()
        self.delete_unmapped_oneview_networks()
        self.synchronize_uplinkset_from_mapped_networks()

    def create_oneview_networks_from_neutron(self):
        print "==============================================================="
        print "==============================================================="
        print "SYNC CREATE SYNC CREATE SYNC CREATE SYNC CREATE SYNC CREATE"
        print "==============================================================="
        print "==============================================================="
        session = get_session(self.connection)
        for network, network_segment in (
            db_manager.list_networks_and_segments_with_physnet(session)
        ):
            id = network.get('id')
            physical_network = network_segment.get('physical_network')
            network_type = network_segment.get('network_type')
            segmentation_id = network_segment.get('segmentation_id')
            print network
            print segmentation_id
            network_dict = common.network_dict_for_network_creation(
                physical_network, network_type, id, segmentation_id
            )
            print "NETWORK DICT:", network_dict
            self.neutron_oneview_client.network.create(session, network_dict)
            print "NETWORK CREATED"

    def synchronize_uplinkset_from_mapped_networks(self):
        print "==============================================================="
        print "==============================================================="
        print "SYNC UPDATE UPLINKSET SYNC UPDATE UPLINKSET"
        print "==============================================================="
        print "==============================================================="
        session = get_session(self.connection)
        for neutron_oneview_network in (
            db_manager.list_neutron_oneview_network(session)
        ):
            oneview_network_id = neutron_oneview_network.oneview_network_id
            neutron_network_id = neutron_oneview_network.neutron_network_id

            network_segment = db_manager.get_network_segment(
                session, neutron_network_id
            )

            self.neutron_oneview_client.network.update_uplinksets(
                session, oneview_network_id, network_segment.get('network_type'),
                network_segment.get('physical_network')
            )
            # uplinkset_uri = self.oneview_client.ethernet_networks.get_associated_uplink_groups(
            #     oneview_network_id
            # )
            # print common.id_list_from_uri_list(uplinkset_uri)
            # print common.uplinkset_id_list_from_oneview_network_uplinkset_list(
            #     db_manager.list_oneview_network_uplinkset(
            #         session, oneview_network_id=oneview_network_id
            #     )
            # )
            # print db_manager.list_oneview_network_uplinkset(
            #     session, oneview_network_id=oneview_network_id
            # )
            # for oneview_network_uplinkset in (
            #     db_manager.list_oneview_network_uplinkset(
            #         session, oneview_network_id=oneview_network_id
            #     )
            # ):
            #     print oneview_network_uplinkset
            #     oneview_network = self.oneview_client.ethernet_networks.get(
            #         oneview_network_uplinkset.oneview_network_id
            #     )
            #     print oneview_network
            #     for uplinkset_uri in self.oneview_client.ethernet_networks.get_associated_uplink_groups()

            print
        # fail()

    def delete_unmapped_oneview_networks(self):
        print "==============================================================="
        print "==============================================================="
        print "SYNC DELETE SYNC DELETE SYNC DELETE SYNC DELETE SYNC DELETE"
        print "==============================================================="
        print "==============================================================="

        session = get_session(self.connection)

        for network in self.oneview_client.ethernet_networks.get_all():
            print network.get('name')
            m = re.search('Neutron\[(.*)\]', network.get('name'))
            if m:
                oneview_network_id = common.id_from_uri(network.get('uri'))
                neutron_network_id = m.group(1)
                print oneview_network_id
                print neutron_network_id

                neutron_network = db_manager.get_neutron_network(
                    session, neutron_network_id
                )
                network_segment = db_manager.get_network_segment(
                    session, neutron_network_id
                )
                print neutron_network
                print network_segment
                print db_manager.list_neutron_networks(session)
                # if neutron_network:
                #     physnet = neutron_network.get('provider:physical_network')
                #     managed = self.neutron_oneview_client.network.is_managed(
                #         physnet
                #     )
                if neutron_network is None:
                    print "NEUTRON NETWORK IS NONE"
                    return self.oneview_client.ethernet_networks.delete(
                        oneview_network_id
                    )
                    # self.neutron_oneview_client.network.delete(
                    #     session, {'id': neutron_network_id}
                    # )
                    # db_manager.delete_neutron_oneview_network(
                    #     session, oneview_network_id=oneview_network_id
                    # )
                else:
                    print "NEUTRON NETWORK IS [[NOT]] NONE"
                    physnet = network_segment.get('physical_network')
                    network_type = network_segment.get('network_type')
                    print "Physical Network:", physnet
                    # print "Is Managed?", self.neutron_oneview_client.network.is_managed(physnet, network_type)
                    if not self.neutron_oneview_client.network.is_managed(
                        physnet, network_type
                    ):
                        print "NEUTRON NETWORK IS NOT MANAGED"
                        return self.oneview_client.ethernet_networks.delete(
                            oneview_network_id
                        )
                    # self.oneview_client.ethernet_networks.delete(
                    #     oneview_network_id
                    # )
