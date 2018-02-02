# Copyright 2017 Hewlett Packard Enterprise Development LP.
# Copyright 2017 Universidade Federal de Campina Grande
# All Rights Reserved.
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

from hpOneView import exceptions
from neutron.tests.unit.plugins.ml2 import _test_mech_agent as base

from networking_oneview.conf import CONF
from networking_oneview.ml2.drivers.oneview import common


@mock.patch.object(common, 'OneViewClient')
class CommonTestCase(base.AgentMechanismBaseTestCase):
    def setUp(self):
        super(CommonTestCase, self).setUp()
        self.allow_insecure_connections = False
        self.ov_manager_url = "https://1.2.3.4"
        self.ov_username = "user"
        self.ov_password = "password"
        self.tls_cacert_file = "cacert_file"

        self.conf = CONF
        self.conf.allow_insecure_connections = self.allow_insecure_connections
        self.conf.oneview.oneview_host = self.ov_manager_url
        self.conf.oneview.username = self.ov_username
        self.conf.oneview.password = self.ov_password
        self.conf.oneview.tls_cacert_file = self.tls_cacert_file

        self.credentials = {
            "ip": self.ov_manager_url,
            "credentials": {
                "userName": self.ov_username,
                "password": self.ov_password
            },
            "ssl_certificate": self.tls_cacert_file
        }

    def test_get_oneview_client(self, mock_oneview_client):
        common.get_oneview_client()
        mock_oneview_client.assert_called_once_with(self.credentials)

    def test_get_oneview_client_insecure_false(self, mock_oneview_client):
        self.conf.oneview.tls_cacert_file = None
        self.assertRaises(
            exceptions.HPOneViewException, common.get_oneview_client)

    def test_get_oneview_client_insecure_cafile(self, mock_oneview_client):
        self.conf.oneview.allow_insecure_connections = True
        self.credentials["ssl_certificate"] = None
        common.get_oneview_client()
        mock_oneview_client.assert_called_once_with(self.credentials)
