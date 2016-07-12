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

from oneview_client import client


@mock.patch.object(client.BaseClient, 'get_session', autospec=True)
def setUp(self, mock_get_session):
    super(OneViewMechanismDriverTestCase, self).setUp()
    cfg.CONF.set_override(
        'manager_url', 'https://1.2.3.4', group='oneview'
    )
    cfg.CONF.set_override('username', 'user', group='oneview')
    cfg.CONF.set_override('password', 'password', group='oneview')
    cfg.CONF.set_override(
        'allow_insecure_connections', True, group='oneview'
    )
    cfg.CONF.set_override('tls_cacert_file', None, group='oneview')
    cfg.CONF.set_override('max_polling_attempts', 12, group='oneview')
    cfg.CONF.set_override('uplinksets_uuid', 'us-uuid', group='oneview')
    self.driver = mech_oneview.OneViewDriver()
    self.driver.initialize()
