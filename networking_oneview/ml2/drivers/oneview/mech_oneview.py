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

from neutron._i18n import _
from neutron.plugins.ml2 import driver_api
from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from neutron.plugins.ml2.drivers.oneview import resources_sync
from oneview_client import client
from oneview_client import exceptions
from oneview_client import models
from oneview_client import utils
from oslo_config import cfg
from oslo_log import log


opts = [
    cfg.StrOpt('manager_url',
               help=_('URL where OneView is available')),
    cfg.StrOpt('username',
               help=_('OneView username to be used')),
    cfg.StrOpt('password',
               secret=True,
               help=_('OneView password to be used')),
    cfg.BoolOpt('allow_insecure_connections',
                default=False,
                help=_('Option to allow insecure connection with OneView')),
    cfg.StrOpt('tls_cacert_file',
               default=None,
               help=_('Path to CA certificate')),
    cfg.IntOpt('max_polling_attempts',
               default=12,
               help=_('Max connection retries to check changes on OneView')),
    cfg.StrOpt('uplinksets_uuid',
               help=_('UplinkSets to be used')),
    cfg.IntOpt('ov_refresh_interval',
               default=3600,
               help=_('Interval between periodic task executions in seconds'))
]


CONF = cfg.CONF
CONF.register_opts(opts, group='oneview')
LOG = log.getLogger(__name__)


class OneViewDriver(driver_api.MechanismDriver):
    def initialize(self):
        self.oneview_client = client.ClientV2(
            CONF.oneview.manager_url,
            CONF.oneview.username,
            CONF.oneview.password,
            allow_insecure_connections=True)
        self._start_resource_sync_periodic_task()

    def _start_resource_sync_periodic_task(self):
        task = resources_sync.ResourcesSyncService(
            self.oneview_client, CONF.database.connection
        )
        task.start(CONF.oneview.ov_refresh_interval)

    def _add_network_to_uplinksets(
        self, uplinksets_uuid, oneview_network_uuid
    ):
        for uplinkset_uuid in uplinksets_uuid:
            self.oneview_client.uplink_set.add_network(
                uplinkset_uuid, oneview_network_uuid
            )

    def remove_inconsistence_from_db(
        self, session, neutron_network_uuid, oneview_network_uuid
    ):
        db_manager.delete_neutron_oneview_network(
            session, neutron_network_uuid
        )
        db_manager.delete_oneview_network_uplinkset(
            session, oneview_network_uuid
        )

    def create_network_postcommit(self, context):
        def prepare_oneview_network_args(name, seg_id):
            kwargs = {
                'name': name,
                'ethernet_network_type': models.EthernetNetwork.UNTAGGED
            }
            if seg_id:
                kwargs['ethernet_network_type'] = models.EthernetNetwork.TAGGED
                kwargs['vlan'] = seg_id

        session = context._plugin_context._session
        neutron_network_dict = context._network
        neutron_network_id = neutron_network_dict.get('id')
        neutron_network_name = neutron_network_dict.get('name')
        neutron_network_seg_id = neutron_network_dict.get(
            'provider:segmentation_id'
        )

        kwargs = prepare_oneview_network_args(
            neutron_network_name, neutron_network_seg_id
        )
        oneview_network_uri = self.oneview_client.ethernet_network.create(
            **kwargs
        )

        oneview_network_uuid = utils.get_uuid_from_uri(oneview_network_uri)

        uplinksets_uuid = CONF.oneview.uplinksets_uuid.split(",")
        self._add_network_to_uplinksets(uplinksets_uuid, oneview_network_uuid)

        db_manager.insert_neutron_oneview_network(
            session, neutron_network_id, oneview_network_uuid
        )
        for uplinkset_uuid in uplinksets_uuid:
            db_manager.insert_oneview_network_uplinkset(
                session, oneview_network_uuid, uplinkset_uuid
            )

    def delete_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network = context._network

        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, neutron_network.get('id')
        )

        try:
            ethernet_network_obj = self.oneview_client.ethernet_network.delete(
                neutron_oneview_network.oneview_network_uuid
            )
        finally:
            self.remove_inconsistence_from_db(
                session, neutron_network.get('id'),
                neutron_oneview_network.oneview_network_uuid
            )

    def update_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network = context._network

        new_network_name = neutron_network.get('name')

        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, neutron_network.get('id')
        )

        if neutron_oneview_network is None:
            return

        try:
            ethernet_network_obj = self.oneview_client.ethernet_network.get(
                neutron_oneview_network.oneview_network_uuid
            )
        except exceptions.OneViewResourceNotFoundError:
            self.remove_inconsistence_from_db(
                session, neutron_network.get('id'),
                neutron_oneview_network.oneview_network_uuid
            )
            LOG.warning("No mapped Network in Oneview")

    def create_port_postcommit(self, context):
        session = context._plugin_context._session
        neutron_port_uuid = context._port.get('id')
        mac = context._port.get('mac_address')
        neutron_network_json = common.get_network_from_port_context(context)
        vnic_type = common.get_vnic_type_from_port_context(context)

        local_link_information_list = common.\
            local_link_information_from_context(
                context._port
            )

        if local_link_information_list is None or\
           len(local_link_information_list) == 0 or\
           vnic_type != 'baremetal':
            return
        elif len(local_link_information_list) > 1:
            raise exception.ValueError(
                "'local_link_information' must have only one value"
            )

        local_link_information_dict = local_link_information_list[0]
        switch_info_dict = local_link_information_dict.get('switch_info')
        server_hardware_uuid = switch_info_dict.get('server_hardware_uuid')
        boot_priority = switch_info_dict.get('boot_priority')

        server_hardware = self.oneview_client.server_hardware.get(
            server_hardware_uuid
        )

        server_profile_uuid = utils.get_uuid_from_uri(
            server_hardware.server_profile_uri
        )

        neutron_oneview_network = db_manager.get_neutron_oneview_network(
            session, neutron_network_json.get("id")
        )

        connection = self.oneview_client.server_profile.add_connection(
            server_profile_uuid,
            neutron_oneview_network.oneview_network_uuid, boot_priority,
            server_hardware.generate_connection_port_for_mac(mac)
        )

        db_manager.insert_neutron_oneview_port(
            session, neutron_port_uuid, server_profile_uuid,
            connection.get('id')
        )

    def _create_port_from_context(self, context, local_link_information):
        session = context._plugin_context._session
        neutron_port_uuid = context._port.get('id')
        mac = context._port.get('mac_address')
        neutron_network_dict = common.get_network_from_port_context(context)
        vnic_type = common.get_vnic_type_from_port_context(context)

        if vnic_type != 'baremetal':
            return

        switch_info_dict = local_link_information.get('switch_info')
        server_hardware_uuid = switch_info_dict.get('server_hardware_uuid')
        boot_priority = switch_info_dict.get('boot_priority')

        server_hardware = self.oneview_client.server_hardware.get(
            server_hardware_uuid
        )

        server_profile_uuid = utils.get_uuid_from_uri(
            server_hardware.server_profile_uri
        )

        server_profile = self.oneview_client.server_profile.get(
            server_profile_uuid
        )

        oneview_network_uplinkset = db_manager.get_oneview_network_uplinkset(
            session, neutron_network_dict.get("id")
        )

        connection = self.oneview_client.server_profile.add_connection(
            server_profile_uuid,
            oneview_network_uplinkset.oneview_network_uuid, boot_priority,
            server_hardware.generate_connection_port_for_mac(mac)
        )

        db_manager.insert_neutron_oneview_port(
            session, neutron_port_uuid, server_profile_uuid,
            connection.get('id')
        )

    def update_port_postcommit(self, context):
        session = context._plugin_context._session
        original_port = context._original_port
        port = context._port
        neutron_port_uuid = port.get('id')

        original_port_mac = original_port.get('mac_address')
        port_mac = port.get('mac_address')

        port_lli = common.first_local_link_information_from_port_context(port)
        original_port_lli = common.\
            first_local_link_information_from_port_context(original_port)

        original_port_boot_priority =\
            common.boot_priority_from_local_link_information(original_port_lli)
        port_boot_priority =\
            common.boot_priority_from_local_link_information(port_lli)

        if not original_port_lli and not port_lli:
            return
        if not original_port_lli and port_lli:
            return self._create_port_from_context(context, port_lli)
        if original_port_lli and not port_lli:
            return self._delete_port_from_context(context)
        if original_port_mac != port_mac or\
           original_port_boot_priority != port_boot_priority:
            neutron_oneview_port = db_manager.get_neutron_oneview_port(
                session, neutron_port_uuid
            )
            server_hardware = self.oneview_client.server_hardware.get(
                common.server_hardware_from_local_link_information(port_lli)
            )
            server_profile_uuid = utils.get_uuid_from_uri(
                server_hardware.server_profile_uri
            )

            return self.oneview_client.server_profile.update_connection(
                server_profile_uuid,
                neutron_oneview_port.oneview_connection_id, port_boot_priority,
                server_hardware.generate_connection_port_for_mac(port_mac)
            )

    def _delete_port_from_context(self, context):
        session = context._plugin_context._session
        neutron_port_uuid = context._port.get('id')
        vnic_type = common.get_vnic_type_from_port_context(context)

        if vnic_type != 'baremetal':
            return

        neutron_oneview_port = db_manager.get_neutron_oneview_port(
            session, neutron_port_uuid
        )

        if neutron_oneview_port:
            self.oneview_client.server_profile.remove_connection(
                neutron_oneview_port.oneview_server_profile_uuid,
                neutron_oneview_port.oneview_connection_id
            )

            db_manager.delete_neutron_oneview_port(session, neutron_port_uuid)

    def delete_port_postcommit(self, context):
        self._delete_port_from_context(context)
