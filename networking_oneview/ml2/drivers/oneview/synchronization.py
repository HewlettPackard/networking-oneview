# Copyright (2016-2017) Hewlett Packard Enterprise Development LP.
# Copyright (2016-2017) Universidade Federal de Campina Grande
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

from hpOneView import exceptions
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_service import loopingcall

from networking_oneview.conf import CONF
from networking_oneview.ml2.drivers.oneview import common
from networking_oneview.ml2.drivers.oneview import database_manager

LOG = log.getLogger(__name__)


class Synchronization(object):
    def __init__(self, oneview_client, neutron_oneview_client,
                 flat_net_mappings):
        self.oneview_client = oneview_client
        self.neutron_client = neutron_oneview_client
        self.flat_net_mappings = flat_net_mappings

    def start(self):
        heartbeat = loopingcall.FixedIntervalLoopingCall(self.synchronize)
        heartbeat.start(
            interval=CONF.DEFAULT.sync_interval,
            initial_delay=0,
            stop_on_exception=False)

    @common.oneview_reauth
    def synchronize(self):
        LOG.info("Starting synchronization mechanism.")
        common.check_valid_resources()
        self.create_oneview_networks_from_neutron()

        force_delete = common.CONF.DEFAULT.force_sync_delete_ops
        LOG.debug("Delete outdated networks and connections operations "
                  "is set to: %s" % force_delete)
        if force_delete:
            self.delete_unmapped_oneview_networks()
            self.synchronize_uplinkset_from_mapped_networks()
            self.recreate_connection()
        LOG.info("Synchronization mechanism finished successfully.")

    def get_oneview_network(self, oneview_net_id):
        try:
            return self.oneview_client.ethernet_networks.get(oneview_net_id)
        except exceptions.HPOneViewException as err:
            LOG.error(err)

    def create_oneview_networks_from_neutron(self):
        LOG.info("Synchronizing Neutron networks not in OneView.")
        session = common.get_database_session()
        for network, network_segment in (
                database_manager.list_networks_and_segments_with_physnet(
                    session)):
            net_id = network.get('id')
            neutron_oneview_network = (
                database_manager.get_neutron_oneview_network(
                    session, net_id))
            if neutron_oneview_network:
                oneview_network = self.get_oneview_network(
                    neutron_oneview_network.oneview_network_id
                )
                if not oneview_network:
                    common.remove_inconsistence_from_db(
                        session,
                        neutron_oneview_network.neutron_network_id,
                        neutron_oneview_network.oneview_network_id
                    )
                else:
                    continue

            physical_network = network_segment.get('physical_network')
            network_type = network_segment.get('network_type')
            segmentation_id = network_segment.get('segmentation_id')
            network_dict = common.network_dict_for_network_creation(
                physical_network, network_type, net_id, segmentation_id
            )

            self.neutron_client.network.create(session, network_dict)

    def synchronize_uplinkset_from_mapped_networks(self):
        LOG.info("Synchronizing OneView uplinksets.")
        session = common.get_database_session()
        for neutron_oneview_network in (
                database_manager.list_neutron_oneview_network(session)):
            oneview_network_id = neutron_oneview_network.oneview_network_id
            neutron_network_id = neutron_oneview_network.neutron_network_id
            network_segment = database_manager.get_network_segment(
                session, neutron_network_id
            )
            if network_segment:
                self.neutron_client.network.update_network_lig(
                    session, oneview_network_id, network_segment.get(
                        'network_type'), network_segment.get(
                            'physical_network'))

    def delete_unmapped_oneview_networks(self):
        LOG.info("Synchronizing outdated networks in OneView.")
        session = common.get_database_session()
        for network in self.oneview_client.ethernet_networks.get_all():
            mmanaged_network = re.search(r'Neutron \[(.*)\]', network.get(
                'name'))
            if mmanaged_network:
                oneview_network_id = common.id_from_uri(network.get('uri'))
                neutron_network_id = mmanaged_network.group(1)
                neutron_network = database_manager.get_neutron_network(
                    session, neutron_network_id
                )
                network_segment = database_manager.get_network_segment(
                    session, neutron_network_id
                )
                if not neutron_network:
                    self.oneview_client.ethernet_networks.delete(
                        oneview_network_id
                    )
                    common.remove_inconsistence_from_db(
                        session, neutron_network_id, oneview_network_id
                    )
                # NOTE(nicodemos) network_segment will always exists?
                # NOTE(mrtenio) network_segments are created by Neutron when
                #  a Network is created. I think we can assume they always
                #  exist
                else:
                    physnet = network_segment.get('physical_network')
                    network_type = network_segment.get('network_type')
                    if not self.neutron_client.network.is_uplinkset_mapping(
                            physnet, network_type):
                        self._delete_connections(neutron_network_id)
                        self.neutron_client.network.delete(
                            session, {'id': neutron_network_id}
                        )

    def _delete_connections(self, neutron_network_id):
        session = common.get_database_session()
        for port, port_binding in (
                database_manager.get_port_with_binding_profile_by_net(
                    session, neutron_network_id)):
            port_dict = common.port_dict_for_port_creation(
                port.get('network_id'), port_binding.get('vnic_type'),
                port.get('mac_address'),
                jsonutils.loads(port_binding.get('profile'))
            )
            local_link_info = common.local_link_information_from_port(
                port_dict)
            server_hardware = (
                common.server_hardware_from_local_link_information_list(
                    self.oneview_client, local_link_info))

            server_profile = (
                self.neutron_client.port.server_profile_from_server_hardware(
                    server_hardware
                )
            )

            self.neutron_client.port.check_server_hardware_availability(
                server_hardware
            )
            previous_power_state = (
                self.neutron_client.port.get_server_hardware_power_state(
                    server_hardware
                )
            )

            self.neutron_client.port.update_server_hardware_power_state(
                server_hardware, "Off")

            for connection in server_profile.get('connections'):
                if connection.get('mac') == port.get('mac_address'):
                    self._remove_connection(
                        server_profile, connection.get('id')
                    )
            self.neutron_client.port.update_server_hardware_power_state(
                server_hardware, previous_power_state
            )

    def _remove_connection(self, server_profile, connection_id):
        connection_primary = False
        connections = []
        for connection in server_profile.get('connections'):
            if connection.get('id') != connection_id:
                connections.append(connection)
            elif connection.get('boot').get('priority') == 'Primary':
                connection_primary = True

        for connection in connections:
            if (connection.get('boot').get('priority') == 'Secondary' and
                    connection_primary):
                connection['boot']['priority'] = 'Primary'

        server_profile_to_update = server_profile.copy()
        server_profile_to_update['connections'] = connections
        self.oneview_client.server_profiles.update(
            resource=server_profile_to_update,
            id_or_uri=server_profile_to_update.get('uri')
        )

    def recreate_connection(self):
        """Recreate connection that were deleted on Oneview.

        Calls method to fix critical connections in the Server Profile that
        will be used.
        """
        LOG.info("Synchronizing connections in OneView Server Profiles.")
        session = common.get_database_session()

        for port, port_binding in (
                database_manager.get_port_with_binding_profile(session)):
            port_dict = common.port_dict_for_port_creation(
                port.get('network_id'),
                port_binding.get('vnic_type'),
                port.get('mac_address'),
                jsonutils.loads(port_binding.get('profile'))
            )
            local_link_info = common.local_link_information_from_port(
                port_dict)
            server_hardware_id = (
                common.server_hardware_from_local_link_information_list(
                    self.oneview_client, local_link_info))
            server_profile = (
                self.neutron_client.port.server_profile_from_server_hardware(
                    server_hardware_id
                )
            )
            neutron_oneview_network = (
                database_manager.list_neutron_oneview_network(
                    session, neutron_network_id=port.get('network_id')))
            connection_updated = False
            if neutron_oneview_network:
                oneview_uri = "/rest/ethernet-networks/" + (
                    neutron_oneview_network[0].oneview_network_id
                )
                self._fix_connections_with_removed_networks(
                    server_profile
                )
                for c in server_profile.get('connections'):
                    if c.get('mac') == port.get('mac_address'):
                        connection_updated = True
                        if c.get('networkUri') != oneview_uri:
                            self._update_connection(
                                oneview_uri, server_profile, c)
            if not connection_updated:
                self.neutron_client.port.create(session, port_dict)

    def _update_connection(
            self, oneview_uri, server_profile, connection):
        server_hardware = self.oneview_client.server_hardware.get(
            server_profile.get('serverHardwareUri')
        )
        connection['networkUri'] = oneview_uri
        self.neutron_client.port.check_server_hardware_availability(
            server_hardware
        )
        previous_power_state = (
            self.neutron_client.port.get_server_hardware_power_state(
                server_hardware
            )
        )
        self.neutron_client.port.update_server_hardware_power_state(
            server_hardware, "Off"
        )
        self.oneview_client.server_profiles.update(
            resource=server_profile,
            id_or_uri=server_profile.get('uri')
        )
        self.neutron_client.port.update_server_hardware_power_state(
            self.oneview_client.server_hardware.get(
                server_profile.get('serverHardwareUri')), previous_power_state
        )

    def _fix_connections_with_removed_networks(self, server_profile):
        sp_cons = []

        server_hardware = self.oneview_client.server_hardware.get(
            server_profile.get('serverHardwareUri')
        )

        for connection in server_profile.get('connections'):
            conn_network_id = common.id_from_uri(
                connection.get('networkUri')
            )
            if self.get_oneview_network(conn_network_id):
                sp_cons.append(connection)

        server_profile['connections'] = sp_cons
        self.neutron_client.port.check_server_hardware_availability(
            server_hardware
        )
        previous_power_state = (
            self.neutron_client.port.get_server_hardware_power_state(
                server_hardware
            )
        )

        self.neutron_client.port.update_server_hardware_power_state(
            server_hardware, "Off"
        )
        self.oneview_client.server_profiles.update(
            resource=server_profile,
            id_or_uri=server_profile.get('uri')
        )
        self.neutron_client.port.update_server_hardware_power_state(
            self.oneview_client.server_hardware.get(
                server_profile.get('serverHardwareUri')), previous_power_state
        )
