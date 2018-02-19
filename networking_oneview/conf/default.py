# Copyright 2018 Hewlett Packard Enterprise Development LP
# Copyright 2018 Universidade Federal de Campina Grande
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

from oslo_config import cfg

CONF = cfg.CONF

opts = [
    cfg.StrOpt('uplinkset_mappings',
               help='UplinkSets to be used.'),
    cfg.StrOpt('flat_net_mappings',
               help='Flat Networks on Oneview that are managed by Neutron.'),
    cfg.IntOpt('sync_interval',
               default=3600,
               help='Interval between synchronization executions in seconds.'),
    cfg.BoolOpt('force_sync_delete_ops',
                default=False,
                help='If set to true, Networking OneView Synchronization is '
                     'allowed to delete outdated network and connections.')
]


def register_opts(conf):
    conf.register_opts(opts, group='DEFAULT')
