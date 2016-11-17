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

from hpOneView.oneview_client import OneViewClient
from neutron._i18n import _
from neutron._i18n import _LW
from neutron.extensions import portbindings
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import driver_api
from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview.neutron_oneview_client import Client
from neutron.plugins.ml2.drivers.oneview import init_sync
from oslo_config import cfg
from oslo_log import log


opts = [
    cfg.StrOpt('oneview_ip',
               help=_('URL where OneView is available')),
    cfg.StrOpt('username',
               help=_('OneView username to be used')),
    cfg.StrOpt('password',
               secret=True,
               help=_('OneView password to be used')),
    cfg.StrOpt('uplinkset_mapping',
               help=_('UplinkSets to be used')),
    cfg.StrOpt('tls_cacert_file', help=_("TLS File Path")),
    cfg.StrOpt('flat_net_mappings',
               default='',
               help=_('-')),
    cfg.IntOpt('ov_refresh_interval',
               default=3600,
               help=_('Interval between periodic task executions in seconds'))
]


CONF = cfg.CONF
CONF.register_opts(opts, group='oneview')

LOG = log.getLogger(__name__)

FLAT_NET = '0'
UPLINKSET = '1'
NETWORK_IS_NONE = '2'


class OneViewDriver(driver_api.MechanismDriver):
    def initialize(self):
        self._initialize_driver()
        self._start_initial_and_periodic_sync_task()

    def _initialize_driver(self):
        self.oneview_client = OneViewClient({
            "ip": CONF.oneview.oneview_ip,
            "credentials": {
                "userName": CONF.oneview.username,
                "password": CONF.oneview.password
            }
        })

        self.neutron_oneview_client = Client(self.oneview_client)

        self.uplinkset_mappings_dict = (
            common.load_conf_option_to_dict(CONF.oneview.uplinkset_mapping)
        )
        self.oneview_network_mapping_dict = (
            common.load_oneview_network_mapping_conf_to_dict(
                CONF.oneview.flat_net_mappings
            )
        )
        if CONF.oneview.tls_cacert_file.strip():
            self.oneview_client.connection.set_trusted_ssl_bundle(
                CONF.oneview.tls_cacert_file
            )

    def _start_initial_and_periodic_sync_task(self):
        task = init_sync.InitSync(
            self.oneview_client, CONF.database.connection
        )
        task.start(CONF.oneview.ov_refresh_interval)

    def create_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network_dict = context._network

        physical_network = neutron_network_dict.get(
            'provider:physical_network'
        )
        provider_network = neutron_network_dict.get('provider:network_type')

        verify_mapping = self.neutron_oneview_client.\
            network.verify_mapping_type(
                physical_network, self.uplinkset_mappings_dict,
                self.oneview_network_mapping_dict
                )

        uplinkset_id_list = (
            self.neutron_oneview_client.uplinkset.filter_by_type(
                self.uplinkset_mappings_dict.get(physical_network),
                provider_network
                )
        )

        if verify_mapping is not FLAT_NET:
            if len(uplinkset_id_list) > 0:
                self.neutron_oneview_client.network.create(
                    session, neutron_network_dict, uplinkset_id_list,
                    self.oneview_network_mapping_dict,
                    self.uplinkset_mappings_dict, commit=False
                )

        elif verify_mapping is FLAT_NET:
            self.neutron_oneview_client.network.create(
                session, neutron_network_dict, uplinkset_id_list,
                self.oneview_network_mapping_dict,
                self.uplinkset_mappings_dict, commit=False
            )

    def delete_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network_dict = context._network

        self.neutron_oneview_client.network.delete(
            session, neutron_network_dict, self.oneview_network_mapping_dict
        )

    def update_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network_id = context._network.get("id")
        new_network_name = context._network.get('name')

        physical_network = context._network.get(
            'provider:physical_network'
        )
        verify_mapping = self.neutron_oneview_client.\
            network.verify_mapping_type(
                physical_network, self.uplinkset_mappings_dict,
                self.oneview_network_mapping_dict
                )
        if verify_mapping is not NETWORK_IS_NONE:
            self.neutron_oneview_client.network.update(
                session, neutron_network_id, new_network_name,
                physical_network, self.uplinkset_mappings_dict,
                self.oneview_network_mapping_dict
            )

    def bind_port(self, context):
        """Bind baremetal port to a network."""
        port = context.current
        vnic_type = port['binding:vnic_type']
        if vnic_type != portbindings.VNIC_BAREMETAL:
            return

        vif_type = portbindings.VIF_TYPE_OTHER
        vif_details = {portbindings.VIF_DETAILS_VLAN: True}
        for segment in context.segments_to_bind:
            vif_details[portbindings.VIF_DETAILS_VLAN] = (
                str(segment[driver_api.SEGMENTATION_ID]))
            context.set_binding(segment[driver_api.ID],
                                vif_type,
                                vif_details,
                                p_const.ACTIVE)
            LOG.debug("OneViewDriver: bound port info- port ID %(id)s "
                      "on network %(network)s",
                      {'id': port['id'],
                       'network': context.network.current['id']})

    def create_port_postcommit(self, context):
        self._create_port_from_context(context)

    def _create_port_from_context(self, context):
        session = context._plugin_context._session
        mac_address = context._port.get('mac_address')

        neutron_network_dict = common.get_network_from_port_context(context)
        neutron_network_id = neutron_network_dict.get('id')
        vnic_type = common.get_vnic_type_from_port_context(context)
        port = context.current
        vnic_type = port['binding:vnic_type']

        if vnic_type != 'baremetal':
            return

        local_link_information_list = common.\
            local_link_information_from_context(
                context._port
            )

        if local_link_information_list is None or\
           len(local_link_information_list) == 0:
            return
        elif len(local_link_information_list) > 1:
            raise exception.ValueError(
                "'local_link_information' must have only one value"
            )

        local_link_information_dict = local_link_information_list[0]

        self.neutron_oneview_client.port.create(
            session, neutron_network_id, mac_address,
            local_link_information_dict
        )

    def update_port_postcommit(self, context):
        session = context._plugin_context._session
        port = context._port
        original_port = context._original_port
        neutron_port_uuid = port.get('id')

        port_lli = common.first_local_link_information_from_port_context(port)
        original_port_lli = common.\
            first_local_link_information_from_port_context(original_port)

        original_port_mac = original_port.get('mac_address')
        port_mac = port.get('mac_address')
        port_boot_priority =\
            common.boot_priority_from_local_link_information(port_lli)
        original_port_boot_priority =\
            common.boot_priority_from_local_link_information(original_port_lli)

        if not original_port_lli and not port_lli:
            return
        if not original_port_lli and port_lli:
            return self._create_port_from_context(context)
        if original_port_lli and not port_lli:
            return self._delete_port_from_context(context)
        if original_port_mac != port_mac or\
           original_port_boot_priority != port_boot_priority:
            return self._create_port_from_context(context)

    def _delete_port_from_context(self, context):
        mac_address = context._port.get('mac_address')
        vnic_type = common.get_vnic_type_from_port_context(context)

        if vnic_type != 'baremetal':
            LOG.debug(
                _("Port with MAC %s is not baremetal. Skipping."), mac_address
            )
            return
        local_link_information_list = common.\
            local_link_information_from_context(
                context._port
            )
        if (local_link_information_list is None or
                len(local_link_information_list) == 0):
            LOG.debug(
                _(
                    "Port with MAC %s does not have local_link_information. "
                    "Skipping."
                ), mac_address
            )
            return
        elif len(local_link_information_list) > 1:
            raise exception.ValueError(
                "'local_link_information' must have only one value"
            )

        local_link_information_dict = local_link_information_list[0]
        switch_info_dict = local_link_information_dict.get('switch_info')

        if switch_info_dict:
            server_hardware_uuid = switch_info_dict.get('server_hardware_uuid')
            if server_hardware_uuid:
                LOG.debug(
                    _("Deleting port with MAC %s from OneView."), mac_address
                )
                self.neutron_oneview_client.port.delete(
                    local_link_information_dict, mac_address
                )
            else:
                LOG.debug(
                    _(
                        "Port with MAC %s switch_info does not contain "
                        "server_hardware_uuid. Skipping."
                    ),
                    mac_address
                )
        else:
            LOG.warning(
                _LW(
                    "Port with MAC %s local_link_information does not contain "
                    "switch_info. Skipping."
                ),
                mac_address
            )

    def delete_port_postcommit(self, context):
        self._delete_port_from_context(context)
