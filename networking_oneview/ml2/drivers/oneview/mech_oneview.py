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

from oslo_log import log
try:
    from neutron_lib.api.definitions import portbindings
    from neutron_lib import constants as p_const
    from neutron_lib.plugins.ml2 import api
except ImportError:
    from neutron.extensions import portbindings
    from neutron.plugins.common import constants as p_const
    from neutron.plugins.ml2 import driver_api as api

from networking_oneview.conf import CONF
from networking_oneview.ml2.drivers.oneview import common
from networking_oneview.ml2.drivers.oneview import neutron_oneview_client
from networking_oneview.ml2.drivers.oneview import synchronization

LOG = log.getLogger(__name__)


class OneViewDriver(api.MechanismDriver):
    def __init__(self):
        self.oneview_client = common.get_oneview_client()
        self.uplinkset_mappings = common.load_conf_option_to_dict(
            CONF.DEFAULT.uplinkset_mappings)
        self.flat_net_mappings = common.load_conf_option_to_dict(
            CONF.DEFAULT.flat_net_mappings)

        common.check_valid_resources()
        common.check_uplinkset_types_constraint(
            self.oneview_client, self.uplinkset_mappings)
        common.check_unique_lig_per_provider_constraint(
            self.uplinkset_mappings)

        self.neutron_oneview_client = neutron_oneview_client.Client(
            self.oneview_client,
            self.uplinkset_mappings,
            self.flat_net_mappings
        )

    def initialize(self):
        common.delete_outdated_flat_mapped_networks(self.flat_net_mappings)
        sync = synchronization.Synchronization(
            oneview_client=self.oneview_client,
            neutron_oneview_client=self.neutron_oneview_client,
            flat_net_mappings=self.flat_net_mappings
        )
        sync.start()

    @common.oneview_reauth
    def bind_port(self, context):
        """Bind baremetal port to a network."""
        session = common.session_from_context(context)
        port_dict = common.port_from_context(context)
        self.neutron_oneview_client.port.create(session, port_dict)

        port = context.current
        vif_type = portbindings.VIF_TYPE_OTHER
        vif_details = {portbindings.VIF_DETAILS_VLAN: True}

        for segment in context.segments_to_bind:
            vif_details[portbindings.VIF_DETAILS_VLAN] = (
                str(segment[api.SEGMENTATION_ID])
            )
            context.set_binding(
                segment[api.ID], vif_type, vif_details, p_const.ACTIVE
            )
            LOG.debug(
                "OneViewDriver: bound port info- port ID %(id)s "
                "on network %(network)s", {
                    'id': port['id'], 'network': context.network.current['id']
                }
            )

    @common.oneview_reauth
    def create_network_postcommit(self, context):
        session = common.session_from_context(context)
        network_dict = common.network_from_context(context)

        self.neutron_oneview_client.network.create(session, network_dict)

    @common.oneview_reauth
    def delete_network_postcommit(self, context):
        session = common.session_from_context(context)
        network_dict = common.network_from_context(context)

        self.neutron_oneview_client.network.delete(session, network_dict)

    @common.oneview_reauth
    def create_port_postcommit(self, context):
        pass

    @common.oneview_reauth
    def delete_port_postcommit(self, context):
        session = common.session_from_context(context)
        port_dict = common.port_from_context(context)

        self.neutron_oneview_client.port.delete(session, port_dict)
