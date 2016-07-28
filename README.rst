=======================================================
HP OneView Mechanism Driver for Neutron ML2 plugin
=======================================================

Overview
=============================
The mechanism driver will interact with Neutron and OneView to
dynamically reflect networking operations made by OpenStack on OneView. With
these operations it's possible to a OneView administrator to know what is
happening in OpenStack System which is running in the Data Center and also
automatizes some operations previously required to be manual.


Install
=============================
1) The ML2 Mechanism Driver:
- Make the git clone of the mechdriver files for a folder of your choice <download_director>:
    $ git clone git@git.lsd.ufcg.edu.br:ironic-neutron-oneview/networking-oneview.git
    
- Access the folder <networking-oneview>:
    $ cd networking-oneview
    
- Run the script install-deriver.sh:
    $ ./install-driver.sh

- This script copy some folders to neutron's work director: /opt/stack/neutron


2) Install python-oneviewclient:
- Clone the python-oneviewclient:
    $ git clone https://github.com/openstack/python-oneviewclient.git

- Access the <python-oneviewclient>

- Run the following command:
    $ git review -d "334119"
    
- Install python-oneviewclient:
    $ sudo python setup.py install


3) Making neutron.conf file configurations: 
- Edit the /etc/neutron/neutron.conf file. Copy the following lines to the end of this file:

[oneview]
manager_url=<path_to_my_OneView>
username=myAdminUserName
password=mySecretOneViewPassword
allow_insecure_connections=true
tls_cacert_file=
uplinksets_uuid=8b4d1932-2528-4f32-8b00-3879cfa1de28
network_mapping=neutron-prov:f0be6758-4b4b-4596-8aa1-6c38d2422d4f
ov_refresh_interval=4

- One example of the manager_url line is:
manager_url=https://10.5.0.20


4) Making setup.cfg file configurations: 
- Edit the /opt/stack/neutron/setup.cfg file. Under: 
    neutron.ml2.mechanism_drivers =
in this file, insert the following:
    oneview = neutron.plugins.ml2.drivers.oneview.mech_oneview:OneViewDriver

 
5) Starting python:
- Start the python:
    $ sudo python setup.py install


6) Making ML2_conf.ini file configurations: 
- Edit the /etc/neutron/plugins/ml2/ml2_conf.ini file. Find the correspondent line and insert the word oneview as follow:
    mechanism_drivers = openvswitch,linuxbridge,genericswitch, oneview


7) Restart Neutron:
- Restart the neutron service. If everything is well, the mechanism driver is working.


8) Creating the database tables:
- Run the migration script to create the database tables necessary for the mechanism driver function.
- Go to the mechanism driver download folder in the following path:
    $ cd <diretorio_download>/networking-oneview/networking_oneview/db
- Then run:
    $ sudo python oneview_network_db.py install

- If any error related to db log occurs, execute:
    $ cd /opt/stack/neutron/
    $ neutron-db-manage upgrade head

