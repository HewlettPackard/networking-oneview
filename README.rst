=======================================================
HP OneView Mechanism Driver for Neutron ML2 plugin
=======================================================

Overview
=============================
The mechanism driver interacts with Neutron and OneView to
dynamically reflect networking operations made by OpenStack on OneView. With
these operations it's possible to a OneView administrator to know what is
happening in OpenStack System which is running in the Data Center and also
automatizes some operations previously required to be manual.


The diagram below provides an overview of how Neutron and OneView will
interact using the Neutron-OneView Mechanism Driver. OneView Mechanism
Driver uses HPE Oneview SDK for Python to provide communication between
Neutron and OneView through OneView's REST API.


Flows:
::

    +---------------------------------+
    |                                 |
    |       Neutron Server            |
    |      (with ML2 plugin)          |
    |                                 |
    |           +---------------------+
    |           |       OneView       |  Ironic API  +----------------+
    |           |      Mechanism      +--------------+     Ironic     |
    |           |       Driver        |              +----------------+
    +-----------+----------+----------+
                           |
                 REST API  |
                           |
                 +---------+---------+
                 |     OneView       |
                 +-------------------+


The Neutron-OneView Mechanism Driver aims at having the Ironic-Neutron 
integration for multi-tenancy working with nodes driven by the OneView 
drivers for Ironic.


How the driver works
=============================

The Neutron-OneView Mechanism Driver considers that not all networking operations that
are performed in OpenStack need to be reflected in OneView. To identify if a certain
request should be executed by the driver it might check if the networks and ports are
related with networks which should be managed by OneView.

For Network Operations the driver checks if the physical provider-network 
the network belongs to is defined as one of the "managed networks" of the
driver. The concept of "managed networks" refeers to the networks configured in
the driver config file with a mapping to attached it to a Uplink Set in OneView.
Operations of Networks with no mappings are just ignored by the driver.

These mappings configuration can be mabe in the configuration file using the
"uplinkset_mappings" and "flat_net_mappings" attributes.

In the case of Port Operations, only ports related to managed networks and with
the "local_link_information" field populated are considered. When the driver
identifies that "local_link_information" exists in a given port, it check if 
it contains a Server Hardware UUID and boot information. The mech driver also
uses the information of the MAC address of the requested port to identify the
specific NIC of the Server Profile where the operation should be executed.
These information can be directly configured in the Neutron port or passed by
Ironic port field "local_link_connection".

Considering these restrictions, OneView Mechanism Driver is capable of:

- Create a network in OneView for each network in Neutron to physical provider-networks configured in the driver config file

- Add networks to Uplink Sets in OneView according to Uplink Set mappings defined to the physical provider-network in the driver config file

    - "Ethernet" Uplink Sets are used with "vlan" typed provider networks
    - "Untagged" Uplink Sets are used with "flat" typed provider networks
    - Other kinds of Uplink Sets neither other types of provider networks are used

- Manual mapping of Neutron flat networks onto specified pre-existing networks of OneView

    - This covers migration from the flat model to the multi-tenant model

- Create, remove and update connections in Server Profiles, implementing Neutron port binding

    - Works only with vif_type = baremetal
    - Expects Server Hardware UUID and boot priority in the local_link_information of the port







Install
=============================

1. The ML2 Mechanism Driver:

- Make the git clone of the mechdriver files for a folder of your choice <download_directory>:
::

    $ git clone git@git.lsd.ufcg.edu.br:ironic-neutron-oneview/networking-oneview.git

- Access the folder <networking-oneview>:
::

    $ cd networking-oneview

- Run the script install-deriver.sh:
::

    $ ./install-driver.sh

- This script copy some folders to neutron's work directory: /opt/stack/neutron


2. Install python-hpOneViewclient:
::

    $ pip install hpOneView


3. Making ML2_conf.ini file configurations: 

- Edit the /etc/neutron/plugins/ml2/ml2_conf.ini file. Find the correspondent line and insert the word *oneview* as follow:
::

    mechanism_drivers = openvswitch,linuxbridge,genericswitch,oneview

- Find the correspondent line and insert the flat physical networks:
::

    [ml2_type_flat]

    flat_networks = public,<flat-physical-network1-name>,<flat-physical-network2-name>*

- Find the correspondent line and insert the vlan physical networks:
::

    [ml2_type_vlan]

    network_vlan_ranges = public,<vlan-physical-network1-name>,<vlan-physical-network2-name>

- Copy the following lines to the end of this file:
::

        [oneview]

        oneview_ip=<OneView server IP address>

        username=<OneView username>

        password=<OneView password>

        uplinkset_mapping=<physical-network1-name>:<oneview-uplinkset1_uuid>,<physical-network2-name>:<uplinkset2_uuid>,...
       
        flat_net_mappings=<flat-physical-network1-name>:<oneview-network1-id>,<flat-physical-network2-name>:<oneview-network2-id>,...
        
        ov_refresh_interval=<ov_refresh_interval> (ov_refresh_interval is used in seconds and is optional - default valeu is 3600)


- Examples of the lines are:
::

    oneview_ip=10.5.0.33

    username=admin

    password=password

    uplinkset_mapping=physnet1:8b4d1932-2528-4f32-8b00-3879cfa1de28,physnet2:f0be6758-4b4b-4596-8aa1-6c38d2422d4f

    flat_net_mappings=physnet3:4e45ab21-ba2e-490a-81f9-2226c240f3d9,physnet4:66666666-ba2e-490a-81f9-2226c240f3d9

    ov_refresh_interval=3600


    [ml2_type_flat]
 
    flat_networks = public,physnet3,physnet4
    
    [ml2_type_vlan]
 
    network_vlan_ranges = public,physnet1,physnet2


4. Making setup.cfg file configurations:

- Edit the /opt/stack/neutron/setup.cfg file. Under: 
::
    
    neutron.ml2.mechanism_drivers =

    in this file, insert the following:

    oneview = neutron.plugins.ml2.drivers.oneview.mech_oneview:OneViewDriver


5. Restart Neutron:

- Restart the neutron service. If everything is well, the mechanism driver is working.


6. Creating the database tables:

- Run the migration script to create the database tables necessary for the mechanism driver function.

- Go to the mechanism driver download folder in the following path:
::

    $ cd <download_directory>/networking-oneview/networking_oneview/db

- Then run:
::

    $ sudo python oneview_network_db.py install

- If any error related to db log occurs, execute:
::

    $ cd /opt/stack/neutron/

    $ neutron-db-manage upgrade head


License
=============================

OneView ML2 Mechanism Driver is distributed under the terms of the Apache
License, Version 2.0. The full terms and conditions of this license are detailed
in the LICENSE file.


Contributing
=============================

You know the drill. Fork it, branch it, change it, commit it, and pull-request
it. We are passionate about improving this project, and glad to accept help to
make it better. However, keep the following in mind:

-  Contributed code must have the same license of the repository.

- We reserve the right to reject changes that we feel do not fit the scope of this project, so for feature additions, please open an issue to discuss your ideas before doing the work.

- If you would like to contribute to the development of OpenStack, you must follow the steps in this page:

    http://docs.openstack.org/infra/manual/developers.html

- Once those steps have been completed, changes to OpenStack should be submitted for review via the Gerrit 
  tool, following the workflow documented at:

    http://docs.openstack.org/infra/manual/developers.html#development-workflow



