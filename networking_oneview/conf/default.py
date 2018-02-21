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
                     'allowed to delete outdated network and connections.'),
    cfg.IntOpt('retries_to_lock_sh',
               default=10,
               help='Maximum number of attempts when trying to lock Server '
                    'Hardware for connection creation.'),
    cfg.IntOpt('retries_to_lock_sh_interval',
               default=30,
               help='Time interval in seconds between attempts when trying '
                    'to lock Server Hardware for connection creation.'),
    cfg.IntOpt('retries_to_lock_sp',
               default=10,
               help='Maximum number of attempts when trying to lock Server '
                    'Hardware for connection creation.'),
    cfg.IntOpt('retries_to_lock_sp_interval',
               default=30,
               help='Time interval in seconds between attempts when trying '
                    'to lock Server Profile for connection creation.')
]


def register_opts(conf):
    conf.register_opts(opts, group='DEFAULT')
