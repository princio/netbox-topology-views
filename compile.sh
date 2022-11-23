#!/bin/bash

if [[ $1 == "all" ]]; then
    yarn --cwd ~/netbox-topology-views/netbox_topology_views/static_dev run bundle

    sudo /opt/netbox/venv/bin/pip install -e ~/netbox-topology-views

    sudo /opt/netbox/venv/bin/python3 /opt/netbox/netbox/manage.py collectstatic --no-input
fi

sudo systemctl restart netbox netbox-rq