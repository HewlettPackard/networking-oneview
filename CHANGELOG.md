# 1.1.0

#### Notes
- Due to the update on the configuration parameters, it is recommended to generate a new one with genrc 

#### Bugfixes & Enhancements
- Abort port delete if its a rack server
- Remove option for 'developer_mode' and add option for 'force_sync_delete_ops'
- Ignore port create if there is no available PXE connections
- Fix import of ML2 constants
- Migrate uplinkset_mappings checks to driver initialization. Driver will not load if:
   - two different physnets have the same mapping LIG:uplinkset
   - the same physnet have two mappings with the same LIG but both uplinks are of the same type
- Keep sync alive even after an Exception occurs
- Move outdated flat network synchronization to driver initialization
- Update log information
- Fail network-creation gracefully if uplinkset already contains a network with same VLAN ID
- Remove unnecessary calls to network creation during synchronization

#### New features
- Move networking oneview configurations to DEFAULT section
- Add new check for resource existence in OneView
- Configure maximum number of attempts when trying to lock Server Hardware and Server Profile for connection creation

# 1.0.0

#### Notes
- This version is expected to work with OpenStack version Ocata or newer

#### Bugfixes & Enhancements
- Reuse Server Profile connection for port creation command
- Update neutron and neutron-lib dependencies
- Update sample configuration file properties
- Update unit tests

#### New features
- Enable secure mode using CA certificate file when opening connections to HPE OneView


# 0.3.2

#### Bugfixes & Enhancements
- Fix neutron_lib import for OpenStack Pike release
- Add warning for port creation with flat network

#### New features
- Reauthenticate with OneView if session expired


# 0.3.1

#### Bugfixes & Enhancements
- Fix port binding import after deprecation of neutron.extensions


# 0.3.0

#### Bugfixes & Enhancements
- Refactoring of synchronization code

#### New features
- Introduces developer mode (disable synchronization operation)


# 0.2.2

#### Bugfixes & Enhancements
- Improve compatibility with python 2 and 3 using six.text_type instead of unicode
- Fix connection change in multi-tenancy environment
- Fix ml2_conf_oneview.ini creation

#### New features
- Add bypass when trying to create port with DL servers


# 0.2.1

#### Bugfixes & Enhancements
- Fix reading of switch_info when in unicode format (input from CLI)


# 0.2.0

#### Bugfixes & Enhancements
- Update periodic synchronization between OpenStack Neutron and HPE OneView resources
- Update mappings and validations

#### New features
- Propagate network CRUD operations to Logical Interconnect Group and all Logical Interconnects associated with it
- New database schema considering LIG and synchronization features
