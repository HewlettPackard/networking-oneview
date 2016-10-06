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

import json
import utils
from neutron._i18n import _LW
from neutron._i18n import _LI
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from neutron.plugins.ml2.drivers.oneview import neutron_oneview_client
from neutron.plugins.ml2.drivers.oneview import common
from oslo_config import cfg
from oslo_service import loopingcall
from oslo_log import log
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import requests
requests.packages.urllib3.disable_warnings()

CONF = cfg.CONF
LOG = log.getLogger(__name__)

FLAT_NET_MAPPING = '0'
UPLINKSET = '1'
NETWORK_IS_NONE = '2'


class InitSync(object):
    def __init__(self, oneview_client, connection):
        self.oneview_client = oneview_client
        self.client = neutron_oneview_client.Client(
            oneview_client
        )
        Session = sessionmaker(bind=create_engine(connection))
        self.session = Session()

        self.uplinkset_mappings_dict = (
            common.load_conf_option_to_dict(CONF.oneview.uplinkset_mapping)
        )
        self.oneview_network_mapping_dict = (
            common.load_oneview_network_mapping_conf_to_dict(
                CONF.oneview.flat_net_mappings
            )
        )

    def start(self, interval):
        heartbeat = loopingcall.FixedIntervalLoopingCall(self.task)
        heartbeat.start(interval=interval, initial_delay=0)

    def task(self):
        LOG.info(_LI("Starting periodic task"))
        self.check_flat_mapped_networks_on_db()
        self.check_changed_ids_flat_mapped_networks()
        self.check_and_sync_deleted_neutron_networks_on_db_and_oneview()
        self.recreate_mapping_between_neutron_and_oneview()
        self.check_mapped_networks_on_db_and_create_on_oneview()
        self.check_and_sync_mapped_uplinksets_on_db()
        self.sync_mapped_uplinksets_on_db()

    def get_oneview_network(self, oneview_network_id):
        try:
            return self.oneview_client.ethernet_networks.get(
                oneview_network_id
            )
        except Exception:
            return None

    def sync_mapped_ports(self, network_id):
        ports_to_be_updated = []
        oneview_id = db_manager.get_neutron_oneview_network(
            self.session,
            network_id).oneview_network_uuid
        for port, port_binding in db_manager.get_port_with_binding_profile(
            self.session, network_id
        ):
            ports_to_be_updated.append(port_binding)
            profile = json.loads(port_binding.get('profile'))
            local_link_information_list = profile.get('local_link_information')
            lli_dict = local_link_information_list[0]
            switch_info_dict = lli_dict.get('switch_info')
            server_hardware_uuid = switch_info_dict.get('server_hardware_uuid')
            server_hardware = self.oneview_client.server_hardware.get(
                common.server_hardware_from_local_link_information(lli_dict)
            )
            server_profile_id = utils.id_from_uri(
                server_hardware.get('serverProfileUri')
            )
            server_profile = self.oneview_client.server_profiles.get(
                server_profile_id
            ).copy()
            for connection in server_profile.get('connections'):
                if connection.get('mac') == port.get('mac_address'):
                    previous_power_state = self.client.port\
                        .get_server_hardware_power_state(
                            server_hardware_uuid
                            )
                    self.client.port.update_server_hardware_power_state(
                        server_hardware_uuid, "Off")
                    connection['networkUri'] = "/rest/ethernet-networks/"\
                        + oneview_id
                    self.oneview_client.server_profiles.update(
                        resource=server_profile,
                        id_or_uri=server_profile.get('uri')
                    )
                    self.client.port.update_server_hardware_power_state(
                        server_hardware_uuid, previous_power_state
                        )

    def sync_ports(self, network_id):
        for port, port_binding in db_manager.get_port_with_binding_profile(
            self.session, network_id
        ):
            profile = json.loads(port_binding.get('profile'))
            local_link_information_list = profile.get('local_link_information')

            if local_link_information_list is None or\
               len(local_link_information_list) == 0:
                continue

            local_link_information_dict = local_link_information_list[0]
            self.client.port.create(
                self.session, port.id, port.network_id, port.mac_address,
                local_link_information_dict
            )

    def sync_mapped_uplinksets_on_db(self):
        for neutron_network, segment in (
            db_manager.list_networks_and_segments_with_physnet(self.session)
        ):
            physnet_compatible_uplinkset_list = (
                self.client.uplinkset.filter_by_type(
                    self.uplinkset_mappings_dict.get(
                        segment.physical_network
                    ),
                    segment.network_type
                )
            )

            neutron_network_dict = {
                'id': neutron_network.id,
                'name': neutron_network.name,
                'provider:segmentation_id': segment.segmentation_id,
                'provider:physical_network': segment.physical_network,
                'provider:network_type': segment.network_type
            }

            neutron_oneview_network = db_manager.get_neutron_oneview_network(
                self.session, neutron_network.id
            )

            if len(physnet_compatible_uplinkset_list) == 0:
                if neutron_oneview_network is not None:
                    self.client.network.delete(
                        self.session, neutron_network_dict,
                        self.oneview_network_mapping_dict
                    )
            elif neutron_oneview_network is None:
                self.client.network.create(
                    self.session, neutron_network_dict,
                    physnet_compatible_uplinkset_list,
                    self.oneview_network_mapping_dict,
                    commit=True, manageable=True
                )
                self.sync_ports(neutron_network.id)
            elif neutron_oneview_network is not None:
                oneview_network_id = (
                    neutron_oneview_network.oneview_network_uuid
                )
                oneview_network_uplink_list = (
                    db_manager.get_network_uplinksets(
                        self.session, oneview_network_id
                    )
                )
                network_uplinkset_list = [
                    network_uplinkset.oneview_uplinkset_uuid
                    for network_uplinkset in oneview_network_uplink_list
                ]

                for uplinkset_id in network_uplinkset_list:
                    if uplinkset_id not in physnet_compatible_uplinkset_list:
                        self.client.uplinkset.remove_network(
                            self.session, uplinkset_id, oneview_network_id
                        )
                        db_manager.delete_neutron_oneview_network(
                            self.session,
                            neutron_oneview_network.neutron_network_uuid,
                            commit=True
                            )

                for uplinkset_id in physnet_compatible_uplinkset_list:
                    if uplinkset_id not in network_uplinkset_list:
                        self.client.uplinkset.add_network(
                            self.session, uplinkset_id, oneview_network_id
                        )

    def check_and_sync_mapped_uplinksets_on_db(self):
        for neutron_network, segment in (
            db_manager.list_networks_and_segments_with_physnet(self.session)
        ):
            physnet_compatible_uplinkset_list = (
                self.client.uplinkset.filter_by_type(
                    self.uplinkset_mappings_dict.get(
                        segment.physical_network
                    ),
                    segment.network_type
                )
            )

            if physnet_compatible_uplinkset_list is None:
                continue
            neutron_oneview_network = db_manager.get_neutron_oneview_network(
                self.session, neutron_network.id
            )
            uplinkset_id_list = (
                self.client.uplinkset.filter_by_type(
                    self.uplinkset_mappings_dict.get(
                        segment.physical_network
                    ),
                    segment.network_type
                )
            )

            if neutron_oneview_network is None:
                neutron_network_dict = {
                    'id': neutron_network.id,
                    'name': neutron_network.name,
                    'provider:segmentation_id': segment.segmentation_id,
                    'provider:physical_network': segment.physical_network,
                    'provider:network_type': segment.network_type
                }

                if len(uplinkset_id_list) > 0:
                    self.client.network.create(
                        self.session, neutron_network_dict, uplinkset_id_list,
                        self.oneview_network_mapping_dict,
                        self.uplinkset_mappings_dict, commit=True,
                        manageable=True
                    )
                else:
                    LOG.warning(_LW(
                        "Physical Network %(physnet)s has no a valid Uplink "
                        "Set associated for type %(type)s" % {
                            'physnet': segment.physical_network,
                            'type': segment.network_type
                        }
                    ))
            else:
                oneview_network_id = (
                    neutron_oneview_network.oneview_network_uuid)
                oneview_network = self.get_oneview_network(
                    oneview_network_id
                )
                oneview_network_uplink_list = (
                    db_manager.get_network_uplinksets(
                        self.session, oneview_network_id
                        ))

                network_uplinkset_list = [
                    network_uplinkset.oneview_uplinkset_uuid
                    for network_uplinkset in oneview_network_uplink_list
                ]
                # Remove network from uplink set and also remove from uplinkset
                # oneview mapping
                for uplinkset_id in network_uplinkset_list:
                    if uplinkset_id not in physnet_compatible_uplinkset_list:
                        self.client.uplinkset.remove_network(
                            self.session, uplinkset_id, oneview_network_id,
                            _commit=True
                        )

                for uplinkset_id in physnet_compatible_uplinkset_list:
                    if uplinkset_id not in network_uplinkset_list:
                        self.client.uplinkset.add_network(
                            self.session, uplinkset_id, oneview_network_id,
                            _commit=True
                        )

    def check_mapped_networks_on_db_and_create_on_oneview(self):
        for neutron_network, segment in (
            db_manager.list_networks_and_segments_with_physnet(self.session)
                ):
            uplinkset_id_list = (
                self.client.uplinkset.filter_by_type(
                    self.uplinkset_mappings_dict.get(
                        segment.physical_network
                    ),
                    segment.network_type
                )
            )
            neutron_oneview_network = db_manager.get_neutron_oneview_network(
                self.session, neutron_network.id
            )
            if (
                neutron_oneview_network is not None or
                    segment.physical_network is None
                    ):
                if neutron_oneview_network.manageable is False:
                    continue
                oneview_network = self.get_oneview_network(
                    neutron_oneview_network.oneview_network_uuid
                )
                if oneview_network is not None:
                    continue
                else:
                    db_manager.delete_neutron_oneview_network(
                        self.session,
                        neutron_oneview_network.neutron_network_uuid)

            neutron_network_dict = {
                'id': neutron_network.id,
                'name': neutron_network.name,
                'provider:segmentation_id': segment.segmentation_id,
                'provider:physical_network': segment.physical_network,
                'provider:network_type': segment.network_type
            }

            uplinkset_id_list = (
                self.client.uplinkset.filter_by_type(
                    self.uplinkset_mappings_dict.get(
                        segment.physical_network
                    ),
                    segment.network_type
                )
            )

            if len(uplinkset_id_list) > 0:
                self.client.network.create(
                    self.session, neutron_network_dict, uplinkset_id_list,
                    self.oneview_network_mapping_dict,
                    self.uplinkset_mappings_dict, commit=True,
                    manageable=True
                )
            else:
                LOG.warning(_LW(
                    "Physical Network %(physnet)s has no a valid Uplink "
                    "Set associated for type %(type)s" % {
                        'physnet': segment.physical_network,
                        'type': segment.network_type
                    }
                ))

    def check_flat_mapped_networks_on_db(self):
        for neutron_network in db_manager.list_neutron_networks(
            self.session
        ):
            segment = db_manager.get_network_segment(
                self.session, neutron_network.id
            )

            verify_mapping = self.client.network.verify_mapping_type(
                segment.physical_network, self.uplinkset_mappings_dict,
                self.oneview_network_mapping_dict
            )
            # The uplinkset_id_list is empty because flat_net_mapping doesn't
            # need to have a mapped uplinkset on database.
            uplinkset_id_list = []

            if verify_mapping is FLAT_NET_MAPPING:
                if db_manager.get_neutron_oneview_network(
                    self.session, neutron_network.id
                )is not None:
                    continue

                neutron_network_dict = {
                    'id': neutron_network.id,
                    'name': neutron_network.name,
                    'provider:segmentation_id': segment.segmentation_id,
                    'provider:physical_network': segment.physical_network,
                    'provider:network_type': segment.network_type
                }
                self.client.network.create(
                    self.session, neutron_network_dict, uplinkset_id_list,
                    self.oneview_network_mapping_dict,
                    self.uplinkset_mappings_dict, commit=True,
                    manageable=False
                )
                self.sync_mapped_ports(neutron_network.id)

    def check_changed_ids_flat_mapped_networks(self):
        for oneview_network_mapped in (
            db_manager.list_neutron_oneview_network_manageable(
                self.session
                )
        ):

            oneview_network_id = oneview_network_mapped.oneview_network_uuid
            neutron_network_id = oneview_network_mapped.neutron_network_uuid

            if oneview_network_id in (
                self.oneview_network_mapping_dict.values()
            ):
                for neutron_network in db_manager.list_neutron_networks(
                    self.session
                ):
                    if neutron_network.id == neutron_network_id:
                        break
                    else:
                        db_manager.delete_neutron_oneview_network(
                            self.session, neutron_network_id
                        )
            else:
                db_manager.delete_neutron_oneview_network(
                    self.session, neutron_network_id
                )

        self.check_flat_mapped_networks_on_db()

    def check_and_sync_deleted_neutron_networks_on_db_and_oneview(self):
        neutron_networks_list = db_manager.list_neutron_networks(self.session)
        for neutron_oneview in (
            db_manager.list_neutron_oneview_network(self.session)
                ):
                if not neutron_oneview.manageable:
                    continue
                isDeleted = True
                neutron_id = neutron_oneview.neutron_network_uuid
                for network in neutron_networks_list:
                    if network.id == neutron_id:
                        isDeleted = False
                        break
                if isDeleted:
                    oneview_network = self.get_oneview_network(
                        neutron_oneview.oneview_network_uuid
                    )
                    if oneview_network is None:
                        self.client.network._remove_inconsistence_from_db(
                            self.session, neutron_id,
                            neutron_oneview.oneview_network_uuid, commit=True
                            )
                        continue
                    self.oneview_client.ethernet_networks.delete(
                        oneview_network
                        )

                    for port in db_manager.list_port_with_network(
                        self.session, neutron_id
                    ):
                        neutron_oneview_port = (
                            db_manager.get_neutron_oneview_port(
                                session, port.id
                            )
                            )
                        sp_id = (
                            neutron_oneview_port.oneview_server_profile_uuid)
                        conn_id = neutron_oneview_port.oneview_connection_id

                        self._remove_connection(sp_id, conn_id)
                        db_manager.delete_neutron_oneview_port(
                            session, port.id)
                    self.client.network._remove_inconsistence_from_db(
                        self.session, neutron_id,
                        neutron_oneview.oneview_network_uuid, commit=True
                    )

    def recreate_mapping_between_neutron_and_oneview(self):
        for neutron_network in (
            db_manager.list_neutron_networks(self.session)
                ):
            oneview_network = self.oneview_client.ethernet_networks.get_by(
                'name', 'Neutron['+neutron_network.id+']')
            if len(oneview_network) > 0:
                oneview_network = oneview_network[0]
                oneview_network_id = utils.id_from_uri(
                    oneview_network.get('uri')
                )
                try:
                    db_manager.insert_neutron_oneview_network(
                        self.session, neutron_network.id, oneview_network_id,
                        commit=True
                        )
                except Exception:
                    self.session.rollback()
                    # print "The network " + oneview_network_id + \
                    #     " is already mapped."
