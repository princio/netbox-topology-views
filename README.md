
# Developing

1. ~/netbox-topology-views/netbox_topology_views/static_dev> yarn run bundle

2. ~/netbox-topology-views> sudo /opt/netbox/venv/bin/pip install -e .

3. \> sudo /opt/netbox/venv/bin/python3 /opt/netbox/netbox/manage.py collectstatic --no-input

4. \> sudo systemctl restart netbox netbox-rq

**Se modifico solo python basta (4), se modifico _js_ devo farli tutti.**

## Come funziona

Prima di tutto si passa per _views.py_, che carica i dati da Netbox e li preprocessa.

L'ultima funzione chiamata in _views.py_ e' `render`, una funzione importata da Django, classicamente utilizzata nel pattern MVC.

Questi dati, fetchati e preprocessati in _views.py_ vengono poi _"plottati"_ in index.html, all'interno di un Element `<script>` sotto forma di formato json.

In index.html, alla fine, viene caricato lo script `app.js`, il quale altro non e' che la versione compilata di `home.js`, attraverso il comando `yarn bundle` ed il file `bundle.js` presenti entrambi in _static\_dev_.

In `home.js` credo avvenga la magia, il quale utilizza il plugin js chiamato _"vis-data"_ e _"vis-network"_.

In pratica, tutto ruota attorno a `topology_data`:
- _views.py_: fetching e preprocessing.
- _index.html_: plotting con il template rendering di Django.
- _home.js_: utilizzo di `topology_data` con il plugin _"vis"_.

## Plugin _Vis_
Plottando per  `Site Osimo`:
- Oggetto 1, che sarebbe un cavo:
```
{
    "id": 1,
    "from": 7,
    "to": 3,
    "title": div
}
```

- Oggetto 2, che sarebbe _Centro Stella Osimo, quindi un device (_router_):
```
{
    "id": 3,
    "image": "../../static/netbox_topology_views/img/router.png",
    "color.border": "#009688",
    "title": div,
    "name": "Centro Stella Osimo",
    "label": "Centro Stella Osimo",
    "shape": "image",
    "physics": false,
    "x": -708,
    "y": -55
}
```

### title: div

E' un div contenente solamente il titolo che viene utilizzato da _vis_ per creare il tooltip in caso di _hover_.

## Ottenere le VLAN

Innanzitutto per ottenere tutti gli oggetti si usano delle classi Singletone sembrerebbe.

Per ottenere tutti i devices: `Device.objects.all()`.

Dal codice sorgente sembra che si possa anche fare `Device.objects.filter()`, ma il plugin mi sembra funzionare diversamente (la usa ma solo per i non Devices).

Per ottere le vlan bisogna chiamare per ogni device `vc_interfaces()`, che riporta una list di tutte le interface associate a quel device.

Poi per ogni _interface_ ci sono due campi, _untagged\_vlan_ e _tagget\_vlan_.

Entrambi i campi sono due classi, entrambe `ipam.VLAN`.

# Netbox Topology Views Plugin

![Version](https://img.shields.io/pypi/v/netbox-topology-views) ![Downloads](https://img.shields.io/pypi/dm/netbox-topology-views)

Create topology views/maps from your devices in netbox.
The connections are based on the cables you created in netbox.
Support to filter on name, site, tag and device role.


## Preview

![preview image](doc/img/preview_3.1.jpeg?raw=true "preview")


## Install

The plugin is available as a Python package and can be installed with pip.

Run `pip install netbox-topology-views` in your virtual env.

To ensure NetBox Topology Views plugin is automatically re-installed during future upgrades, create a file named `local_requirements.txt` (if not already existing) in the NetBox root directory (alongside `requirements.txt`) and list the `netbox-topology-views` package:

```no-highlight
# echo netbox-topology-views >> local_requirements.txt
```

Once installed, the plugin needs to be enabled in your `configuration.py`

```python
# In your configuration.py
PLUGINS = ["netbox_topology_views"]
```

First run `source /opt/netbox/venv/bin/activate` to enter the Python virtual environment.

Then run 
```bash
cd /opt/netbox/netbox
pip3 install netbox-topology-views
python3 manage.py collectstatic --no-input
```


### Versions

| netbox version        | netbox-topology-views version          |
| ------------- |-------------|
| >= 3.3.0 | >= v3.0.0 |
| >= 3.2.0 | >= v1.1.0 |
| >= 3.1.8 | >= v1.0.0 |
| >= 2.11.1 | >= v0.5.3 |
| >= 2.10.0 | >= v0.5.0 |
| < 2.10.0 | =< v0.4.10 |


### Custom field: coordinates

There is also support for custom fields.

If you create a custom field "coordinates" for "dcim > device" and "Circuits > circuit" with type "text" and name "coordinates" you will see the same layout every time. It is recommended to set this field to "UI visibility" "Hidden" and let the plugin manage it in the background.

The coordinates are stored as: "X;Y".

Please read the "Configure" chapter to set the `allow_coordinates_saving` option to True.
You might also set the `always_save_coordinates` option to True.


## Configure

If you want to override the default values configure the `PLUGINS_CONFIG` in your `netbox configuration.py`.

Example:
```
PLUGINS_CONFIG = {
    'netbox_topology_views': {
        'device_img': ['router','switch', 'firewall'],
        'preselected_device_roles': ['Router', 'Firewall']
    }
}
```

| Setting        | Default value           | Description  |
| ------------- |-------------| -----|
| device_img      |['access-switch', 'core-switch', 'firewall', 'router', 'distribution-switch', 'backup', 'storage,wan-network', 'wireless-ap', 'server', 'internal-switch', 'isp-cpe-material', 'non-racked-devices', 'power-units'] | The slug of the device roles that you have a image for. |
| preselected_device_roles      | ['Firewall', 'Router', 'Distribution Switch', 'Core Switch', 'Internal Switch', 'Access Switch', 'Server', 'Storage', 'Backup', 'Wireless AP'] | The full name of the device roles you want to pre select in the global view.  Note that this is case sensitive|
| allow_coordinates_saving      | False | (bool) Set to true if you use the custom coordinates fields and want to save the coordinates |
| always_save_coordinates       | False | (bool) Set if you want to enable the option to save coordinates by default |
| ignore_cable_type      | [] | The cable types that you want to ignore in the views  |
| preselected_tags      | '[]' | The name of tags you want to preload  |
| draw_default_layout | False | (bool) Set to True if you want to load draw the topology on the initial load (when you go to the topology plugin page) |


### Custom Images

You upload you own custom images to the netbox static dir (`static/netbox_topology_views/img/`).
These images need to be named after de device role slug and have the .png format/extension.
If you add your own image you also need to add the slug to the `device_img` setting.


## Use

Go to the plugins tab in the navbar and click topology or go to `$NETBOX_URL/plugins/netbox_topology_views/` to view your topologies


### Update

Run `pip install netbox-topology-views --upgrade` in your venv.

Run `python3 manage.py collectstatic --no-input`

Clear you browser cache.


### Permissions

To view `/plugins/topology-views/` you need the following permissions:
 + dcim | device | can view device
 + dcim | site | can view site
 + extras | tag | can view tag
 + dcim | device role | can view device role


## Icons info

Power icons created by [Freepik - Flaticon](https://www.flaticon.com/free-icons/power).

Power icons created by [Flat Icons - Flaticon](https://www.flaticon.com/free-icons/power)

Provider icons created by [Good Ware - Flaticon](https://www.flaticon.com/free-icons/provider)

