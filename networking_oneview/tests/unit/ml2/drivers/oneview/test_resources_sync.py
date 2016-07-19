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


import mock
import unittest

from neutron.db.models_v2 import Network
from neutron.db import oneview_network_db
from neutron.db.segments_db import NetworkSegment
from neutron.plugins.ml2.drivers.oneview import database_manager as db_manager
from neutron.plugins.ml2.drivers.oneview import resources_sync
from oneview_client import client
from oneview_client import managers
from oneview_client import models
from sqlalchemy import orm
from sqlalchemy.orm import session


CONNECTION = 'mysql+pymysql://server/database'


class TestResourcesSync(unittest.TestCase):

    @mock.patch.object(client.BaseClient, 'get_session')
    def _get_oneview_client(self, mock_session):
        return client.ClientV2(
            manager_url='https://something', username='user', password='pass'
        )

    @mock.patch.object(orm, 'sessionmaker')
    def setUp(self, mock_sessionmaker):
        self.oneview_client = self._get_oneview_client()
        self.resources_sync = resources_sync.ResourcesSyncService(
            self.oneview_client, CONNECTION
        )

    @mock.patch.object(db_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(session.Session, 'commit', autospec=True)
    def test_delete_network_from_db(
        self, mock_commit, mock_delete_neutron_oneview_network
    ):
        neutron_network_uuid = 'neutron-uuid'
        oneview_network_uuid = 'oneview-uuid'
        neutron_oneview_network = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_uuid, oneview_network_uuid
        )
        self.resources_sync.delete_network_from_db(neutron_oneview_network)
        mock_delete_neutron_oneview_network.assert_called_once_with(
            self.resources_sync.session, neutron_network_uuid
        )
        mock_commit.assert_called_once_with(self.resources_sync.session)

    @mock.patch.object(managers.EthernetNetworkManager, 'delete')
    @mock.patch.object(db_manager, 'delete_neutron_oneview_network')
    @mock.patch.object(session.Session, 'commit', autospec=True)
    def test_delete_network_from_oneview_and_db(
        self, mock_commit, mock_delete_neutron_oneview_network, mock_delete
    ):
        neutron_network_uuid = 'neutron-uuid'
        oneview_network_uuid = 'oneview-uuid'
        neutron_oneview_network = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_uuid, oneview_network_uuid
        )

        self.resources_sync.delete_network_from_oneview_and_db(
            neutron_oneview_network
        )

        mock_delete_neutron_oneview_network.assert_called_once_with(
            self.resources_sync.session, neutron_network_uuid
        )
        mock_commit.assert_called_once_with(self.resources_sync.session)
        mock_delete.assert_called_once_with(oneview_network_uuid)

    @mock.patch.object(db_manager, 'get_neutron_network')
    @mock.patch.object(db_manager, 'get_network_segment')
    @mock.patch.object(session.Session, 'commit', autospec=True)
    @mock.patch.object(managers.EthernetNetworkManager, 'create')
    def test_create_untagged_network_in_oneview(
        self, mock_create, mock_commit, mock_get_network_segment,
        mock_get_neutron_network
    ):
        neutron_network_uuid = 'neutron-uuid'
        oneview_network_uuid = 'oneview-uuid'
        neutron_oneview_network = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_uuid, oneview_network_uuid
        )

        neutron_network = Network()
        network_segment = NetworkSegment()
        mock_get_neutron_network.return_value = neutron_network
        mock_get_network_segment.return_value = network_segment
        neutron_network.name = "name"

        self.resources_sync.create_network_in_oneview(neutron_oneview_network)

        mock_get_neutron_network.assert_called_once_with(
            self.resources_sync.session, neutron_network_uuid
        )
        mock_get_network_segment.assert_called_once_with(
            self.resources_sync.session, neutron_network_uuid
        )

        oneview_network_uri = "oneview_network_uri"

        mock_create.return_value = oneview_network_uri

        mock_create.assert_called_once_with(
            name=neutron_network.name,
            ethernet_network_type=models.EthernetNetwork.UNTAGGED
        )
        mock_commit.assert_called_once_with(self.resources_sync.session)

    @mock.patch.object(db_manager, 'get_neutron_network')
    @mock.patch.object(db_manager, 'get_network_segment')
    @mock.patch.object(session.Session, 'commit', autospec=True)
    @mock.patch.object(managers.EthernetNetworkManager, 'create')
    def test_create_tagged_network_in_oneview(
        self, mock_create, mock_commit, mock_get_network_segment,
        mock_get_neutron_network
    ):
        neutron_network_uuid = 'neutron-uuid'
        oneview_network_uuid = 'oneview-uuid'
        neutron_oneview_network = oneview_network_db.NeutronOneviewNetwork(
            neutron_network_uuid, oneview_network_uuid
        )

        neutron_network = Network()
        network_segment = NetworkSegment()
        mock_get_neutron_network.return_value = neutron_network
        mock_get_network_segment.return_value = network_segment
        neutron_network.name = "name"
        network_segment.segmentation_id = "id"

        self.resources_sync.create_network_in_oneview(neutron_oneview_network)

        mock_get_neutron_network.assert_called_once_with(
            self.resources_sync.session, neutron_network_uuid
        )
        mock_get_network_segment.assert_called_once_with(
            self.resources_sync.session, neutron_network_uuid
        )

        oneview_network_uri = "oneview_network_uri"

        mock_create.return_value = oneview_network_uri

        mock_create.assert_called_once_with(
            name=neutron_network.name,
            ethernet_network_type=models.EthernetNetwork.TAGGED,
            vlan=network_segment.segmentation_id
        )
        mock_commit.assert_called_once_with(self.resources_sync.session)
