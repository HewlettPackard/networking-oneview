# Copyright 2016 OpenStack Foundation
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
#

"""neutron_network_oneview

Revision ID: 64c974fb52b0
Revises: d3435b514502
Create Date: 2016-06-16 13:25:08.761553

"""

# revision identifiers, used by Alembic.
revision = '64c974fb52b0'
down_revision = 'd3435b514502'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('neutron_oneview_network',
        sa.Column('neutron_network_uuid', sa.String(length=36)),
        sa.Column('oneview_network_uuid', sa.String(length=36)),
        sa.PrimaryKeyConstraint('neutron_network_uuid')
    )
    
    op.create_table('oneview_network_uplinkset',
        sa.Column('oneview_network_uuid', sa.String(length=36)),
        sa.Column('oneview_uplinkset_uuid', sa.String(length=36)),
        sa.PrimaryKeyConstraint('oneview_network_uuid','oneview_uplinkset_uuid')
    )

    op.create_table('neutron_oneview_port',
        sa.Column('neutron_port_uuid', sa.String(length=36)),
        sa.Column('oneview_server_profile_uuid', sa.String(length=36)),
        sa.Column('oneview_connection_id', sa.String(length=36)),
        sa.PrimaryKeyConstraint('neutron_port_uuid')
    )


