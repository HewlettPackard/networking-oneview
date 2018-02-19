[![PyPI version](https://badge.fury.io/py/networking-oneview.svg)](https://badge.fury.io/py/networking-oneview)
[![Build Status](https://travis-ci.org/HewlettPackard/networking-oneview.svg?branch=master)](https://travis-ci.org/HewlettPackard/networking-oneview)
[![Coverage Status](https://codecov.io/gh/HewlettPackard/networking-oneview/branch/master/graphs/badge.svg)](https://codecov.io/gh/HewlettPackard/networking-oneview)

HPE OneView Mechanism Driver
============================

Overview
--------

The Mechanism Driver dynamically reflects some networking operations
made by [OpenStack Neutron](https://wiki.openstack.org/wiki/Neutron) to
[HPE
OneView](https://www.hpe.com/us/en/integrated-systems/software.html).
These operations allows the OneView administrator to know what is
happening in the OpenStack System, and automatizes some operations.

The following diagram describes an overview of how Neutron and OneView
will interact using the Mechanism Driver. This driver uses
python-hpOneView to provide communication between Neutron and OneView
via REST API.

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

The OneView Mechanism Driver aims at having the Ironic-Neutron
integration for multi-tenancy working with nodes driven by the OneView
drivers for Ironic.

How the driver works
--------------------

The OneView Mechanism Driver does not reflect all networking operations
in Neutron to OneView. To identify if a certain Neutron request should
be fulfilled, the Mechanism Driver checks if the networks and ports are
related with networks/connections created on OneView.

There are two cases regarding the usage of networks (both properties are
in the configuration file detailed in the following):

​1. When the user wants to map a Neutron provider network to the
OneViewUplinkSet, so that every network/port operation on this provider
network will be reflected (created) on OneView. This mapping is made
using the uplinkset\_mappings property. In this situation the
administrator defines comma-separated triples of:

    uplinkset_mappings=<provider_network>:<logical_interconnect_group_uuid>:<uplink_set_name>

These can be related to two types of Uplink Sets:

-   Ethernet Uplink Sets - to support VLAN networks.
-   Untagged Uplink Sets - to support flat network.

​2. When the user wants Neutron to be aware of a previously created
network on OneView, so that this network will be mapped onto a provider
network, and every port/connection operation using that provider network
will use the mapped network to attach to the connection on OneView. In
this situation the administrator defines comma-separated pairs of:

    flat_net_mappings=<neutron_provider_network>:<oneview_network_uuid>

In the case of port operations, only Neutron ports related to managed
networks with the *local\_link\_information* field populated are
considered. The mechanism driver also uses the information from the MAC
address of the requested port, to identify the specific NIC of the
Server Profile where the operation should be executed. This information
can be directly configured in the Neutron port or passed by the Ironic
port field *local\_link\_connection*.

The driver also implements a fault tolerance process to guarantee that
all networks and ports that are present in Neutron are correctly
reflected in OneView. To ensure that, the verification is executed in
the startup of the mechanism driver and periodically after the
initialization. This synchronization process considers the information
from the configuration file, and the information stored in the OneView
Mechanism Driver tables present in the Neutron Database.

Considering these assumptions, OneView Mechanism Driver is capable of
the following:

-   **Create a network** in OneView for each network creation request in
    Neutron to the physical provider-networks configured in the driver
    config file.
-   **Add networks to Uplink Sets** in OneView for the mapped Uplink Set
    to the physical provider-network in the driver config file.

    > -   Ethernet Uplink Sets are used with vlan typed provider
    >     networks
    > -   Untagged Uplink Sets are used with flat typed provider
    >     networks

-   **Manual mapping** of Neutron flat networks onto specified
    pre-existing networks of OneView.
-   **Create, remove, and update connections** in Server Profiles,
    implementing Neutron port binding.

    > -   Works only when Neutron port with binding\_vnic\_type =
    >     baremetal
    > -   Expects Server Hardware ID and boot priority in the
    >     local\_link\_information of the Ironic port

-   **Synchronization** of all networks and ports/connections, to
    provide fault tolerance.

Ironic Configuration
--------------------

By default, Ironic is configured to use flat networks during the
deployment process. In order to use Ironic-Neutron integration to
provide networks isolation during deployment, some configuration is
necessary. In the ironic.conf file the following configuration should be
done:

    [DEFAULT]
    enabled_network_interfaces = flat,noop,neutron
    default_network_interface = neutron

    [neutron]
    cleaning_network = <neutron_cleaning_network>
    provisioning_network = <neutron_provisioning_network>

As mentioned in the previous section, the OneView Mechanism Driver needs
to receive the `local_link_connection` from Ironic ports to perform
networking ports operations. Once Ironic ports do not have any
information stored by default, it is necessary to update ports with the
local-link-connection:

    openstack baremetal port set <port_uuid> --node <node> --local-link-connection switch_id=<switch_id> --local-link-connection switch_info='"{\"server_hardware_id\": \"<sh_id>\", \"bootable\": \"True\"}"' --local-link-connection port_id='' --pxe-enabled true

> **note**
>
> The Ironic OneView CLI creates Ironic ports and set
> “local\_link\_connection”.

**local\_link\_connection attributes**

-   switch\_id: required, but the OneView Mechanism Driver does not deal
    directly with switches. switch\_id receives any value in MAC format.
    Example: 01:23:45:67:89:ab
-   port\_id : required, but the OneView Mechanism Driver does not deal
    directly. port\_id receives any value.
-   switch\_info: will be configured with information demanded by
    OneView Mechanism Driver.

    > -   server\_hardware\_id: identifies in which Server Hardware the
    >     connection to represent the new port will be created
    > -   bootable: indicates if this connection will be bootable or
    >     not. It is required for performance deploy.

To identify the port where the connection needs to be created, the MAC
address already configured in the Ironic port will be used.

Install using OpenStack
-----------------------

To install the OneView Mechanism Driver, access the virtual environment
on Neutron Server Container:

    $ source /openstack/venvs/<neutron_venv>/bin/activate

To install the OneView Mechanism Driver, run:

    $ pip install networking-oneview

Configuration
-------------

1.  To configure Neutron ML2 plugin, access the file:

    /etc/neutron/plugins/ml2/ml2\_conf.ini

-   Add the OneView driver:

        mechanism_drivers = <other_drivers>,oneview

1.1 On both containers (Neutron Server and Neutron Agent):

-   Insert the networks flat,vlan:

        tenant_network_types = vxlan,flat,vlan

-   Insert the flat physical networks:

        [ml2_type_flat]

        flat_networks = public,<flat-physical-network1>,<flat-physical-network2>

-   Insert the vlan physical networks:

        [ml2_type_vlan]

        network_vlan_ranges = public,<vlan-physical-network1>,<vlan-physical-network2>

2.  To configure the OneView configuration, access the file:

    /etc/neutron/plugins/ml2/ml2\_conf\_oneview.ini

> **note**
>
> If you are using TLS options for communication with OneView; it is
> necessary to download the credentials (appliance.com.crt) from OneView

    oneview_host=<hostname>
    username=<username>
    password=<password>
    uplinkset_mappings=<provider:logical_interconnect_group_id:uplink_name>,<provider2:logical_interconnect_group_id2:uplink_name2>
    flat_net_mappings=<provider3:oneview_network_id>,<provider4:oneview_network_id2>
    ov_refresh_interval=<oneview_refresh_internal>
    tls_cacert_file = <cacert_file_path>

3.  In Neutron Agent, edit:

    /etc/neutron/plugins/ml2/linuxbridge\_agent.ini

Map neutron ports used by the container as follow:

    [linux_bridge]
    physical_interface_mappings = <flat-physical-network1-name:network-interface>,<vlan-physical-network1-name:network-interface>

4.  Upgrading Neutron Database:

-   Upgrade database:

        $ neutron-db-manage upgrade heads

-   Edit the /etc/systemd/system/\<neutron\_directory\>.service file.
    :   -   In the property ExecStart add:

            --config-file
            /etc/neutron/plugins/ml2/ml2\_conf\_oneview.ini

-   Restart the neutron service:

        $ systemctl daemon-reload && service neutron-server restart

-   Restart the neutron-agent container:

        $ service neutron-linuxbridge-agent restart

5.  Configuring haproxy timeout in the outside container (host):

-   To set the time on haproxy, edit both files:

        /etc/haproxy/conf.d/00-haproxy
        /etc/haproxy/haproxy.cfg

-   In the defaults section of the files, change the following lines to:

        timeout client 300s
        timeout connect 10s
        timeout server 300s

-   Restart the haproxy service:

        $ service haproxy restart

License
-------

OneView ML2 Mechanism Driver is distributed under the terms of the
Apache License, Version 2.0. The full terms and conditions of this
license are detailed in the LICENSE file.

Contributing
------------

Fork it, branch it, change it, commit it, and pull-request it. We are
passionate about improving this project, and are glad to accept help to
make it better. However, keep the following in mind: We reserve the
right to reject changes that we feel do not fit the scope of this
project. For feature additions, please open an issue to discuss your
ideas before doing the work.

Feature Requests
----------------

If you have a need not being met by the current implementation, please
let us know (via a new issue). This feedback is crucial for us to
deliver a useful product. Do not assume that we have already thought of
everything, because we assure you that is not the case.
