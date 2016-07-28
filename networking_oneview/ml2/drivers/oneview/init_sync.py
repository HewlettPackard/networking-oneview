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

from neutron._i18n import _LW
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from neutron.plugins.ml2.drivers.oneview import neutron_oneview_client
from neutron.plugins.ml2.drivers.oneview import common
from oslo_config import cfg
from oslo_log import log
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
#
CONF = cfg.CONF
LOG = log.getLogger(__name__)


class InitSync(object):
    def __init__(self, oneview_client, connection):
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

    def check_mapped_networks_on_db_and_create_on_oneview(self):
        for neutron_network in db_manager.list_neutron_networks(
            self.session
        ):
            segment = db_manager.get_network_segment(
                self.session, neutron_network.id
            )

            if db_manager.get_neutron_oneview_network(
                self.session, neutron_network.id
            ) is not None or segment.physical_network is None:
                continue

            neutron_network_dict = {
                'id': neutron_network.id,
                'name': neutron_network.name,
                'provider:segmentation_id': segment.segmentation_id,
                'provider:physical_network': segment.physical_network,
                'provider:network_type': segment.network_type
            }

            uplinkset_id_list = (
                self.client.uplinkset.get_uplinkset_by_type(
                    self.uplinkset_mappings_dict.get(
                        segment.physical_network
                    ),
                    segment.network_type
                )
            )

            if len(uplinkset_id_list) > 0:
                self.client.network.create(
                    self.session, neutron_network_dict, uplinkset_id_list,
                    self.oneview_network_mapping_dict
                )
            else:
                LOG.warning(_LW(
                    "Physical Network %(physnet)s has no a valid Uplink "
                    "Set associated for type %(type)s" % {
                        'physnet': segment.physical_network,
                        'type': segment.network_type
                    }
                ))
