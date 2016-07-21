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

from neutron._i18n import _, _LW
from neutron.plugins.ml2 import driver_api
from neutron.plugins.ml2.drivers.oneview import common
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from neutron.plugins.ml2.drivers.oneview.neutron_oneview_client import Client
from neutron.plugins.ml2.drivers.oneview import resources_sync
from oneview_client import client
from oneview_client import exceptions
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


class OneViewDriver(driver_api.MechanismDriver):
    def initialize(self):
        self.oneview_client = client.ClientV2(
            CONF.oneview.manager_url,
            CONF.oneview.username,
            CONF.oneview.password,
            allow_insecure_connections=True)
        self.neutron_oneview_client = Client(self.oneview_client)

        self._load_conf()
        self._start_resource_sync_periodic_task()

    def _load_conf(self):
        uplinksets_uuid = CONF.oneview.uplinksets_uuid
        self.uplinksets_uuid_list = []
        if uplinksets_uuid is not None and uplinksets_uuid.strip():
            self.uplinksets_uuid_list = uplinksets_uuid.split(",")

        oneview_network_mapping = CONF.oneview.flat_net_mappings
        self.oneview_network_mapping_list = []
        if oneview_network_mapping is not None and\
           oneview_network_mapping.strip():
            self.oneview_network_mapping_list =\
                oneview_network_mapping.split(",")

    def _start_resource_sync_periodic_task(self):
        task = resources_sync.ResourcesSyncService(
            self.oneview_client, CONF.database.connection
        )
        task.start(CONF.oneview.ov_refresh_interval)

    def create_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network_dict = context._network

        self.neutron_oneview_client.network.create(
            session, neutron_network_dict, self.uplinksets_uuid_list,
            self.oneview_network_mapping_list
        )

    def delete_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network_dict = context._network

        self.neutron_oneview_client.network.delete(
            session, neutron_network_dict, self.uplinksets_uuid_list,
            self.oneview_network_mapping_list
        )

    def update_network_postcommit(self, context):
        session = context._plugin_context._session
        neutron_network_id = context._network.get("id")
        new_network_name = context._network.get('name')

        self.neutron_oneview_client.network.update(
            session, neutron_network_id, new_network_name
        )

    def create_port_postcommit(self, context):
        self._create_port_from_context(context)

    def _create_port_from_context(self, context):
        session = context._plugin_context._session
        neutron_port_uuid = context._port.get('id')
        mac_address = context._port.get('mac_address')
        vnic_type = common.get_vnic_type_from_port_context(context)

        if vnic_type != 'baremetal':
            return

        local_link_information_list = common.\
            local_link_information_from_context(
                context._port
            )

        self.neutron_oneview_client.port.create(
            session, neutron_port_uuid, neutron_network_id, mac_address,
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
            self.neutron_oneview_client.port.update(
                session, neutron_port_uuid, port_lli, port_boot_priority,
                port_mac
            )

    def _delete_port_from_context(self, context):
        session = context._plugin_context._session
        neutron_port_uuid = context._port.get('id')
        vnic_type = common.get_vnic_type_from_port_context(context)

        if vnic_type != 'baremetal':
            return

        self.neutron_oneview_client.port.delete(session, neutron_port_uuid)

    def delete_port_postcommit(self, context):
        self._delete_port_from_context(context)
