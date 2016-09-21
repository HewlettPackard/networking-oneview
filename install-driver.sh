NEUTRON_DIR=${1:-/opt/stack/neutron}

cp -r networking_oneview/db $NEUTRON_DIR/neutron/
cp -r networking_oneview/ml2 $NEUTRON_DIR/neutron/plugins/
cp -r networking_oneview/tests/unit/ml2 $NEUTRON_DIR/neutron/tests/unit/plugins

cd $NEUTRON_DIR 
sudo python setup.py install
