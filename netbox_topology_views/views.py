import math
from django.shortcuts import render
from django.db.models import Q
from django.views.generic import View
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.conf import settings
from django.http import QueryDict
from django.http import HttpResponseRedirect


from .forms import DeviceFilterForm
from .filters import DeviceFilterSet

import json

from dcim.filtersets import DeviceRoleFilterSet
from dcim.models import Device, CableTermination, DeviceRole,  Interface, FrontPort, RearPort, PowerPanel,  PowerFeed
from circuits.models import CircuitTermination
from wireless.models import WirelessLink
from extras.models import Tag
from ipam.models import VLAN, IPAddress, Prefix

import logging
import random

from typing import cast, List, Union

logger = logging.getLogger(f"django.template")

supported_termination_types = ["interface", "front port", "rear port", "power outlet", "power port", "console port", "console server port"]

vid_colors = {}
def random_color(vid: int):
    if vid not in vid_colors:
        r = random.randint(0,255)
        g = random.randint(0,255)
        b = random.randint(0,255)
        vid_colors[vid] = f'rgb({r}, {g}, {b})'
    return vid_colors[vid]

def get_parent_prefix(ip) -> Union[Prefix,None]:
    prefixes= [prefix for prefix in Prefix.objects.filter(
            vrf=ip.vrf,
            prefix__net_contains_or_equals=str(ip.address.ip)
        )]
    return None if len(prefixes) == 0 else cast(Prefix, prefixes[0])

def get_device_ip(ip: IPAddress):
    aot = ip.assigned_object_type
    if aot is None:
        return None
    if aot.model != 'interface':
        logger.warn(f'IP {ip} have not assigned an "interface" but a {aot.model}.')
        return None
    interface = cast(Interface, ip.assigned_object)
    device = interface.device
    return device
    


def nodes(use_coordinates):
    COLORS = { 'Router': 'blue', 'Firewall': 'red', 'Prefix': 'black'}
    SHAPES = { 'Router': 'hexagon', 'Firewall': 'hexagon', 'Prefix': 'circle'}
    nodes = {}
    edges = []
    def add_coordinates(node, obj: Union[Prefix, Device]):
        if not use_coordinates:
            return node
        if "coordinates" in obj.custom_field_data:
            if obj.custom_field_data["coordinates"] is not None:
                if ";" in obj.custom_field_data["coordinates"]:
                    cords =  obj.custom_field_data["coordinates"].split(";")
                    node["x"] = int(cords[0])
                    node["y"] = int(cords[1])
                    node["physics"] = not use_coordinates
        return node

    def add_device(device: Device) -> str:
        id_ = f'device_{device.pk}'
        node = {
            'id': id_,
            'netbox_id': device.pk,
            'n_edges': 0,
            'name': device.name,
            'label': device.name,
            'type': 'device',
            'shape': SHAPES[device.device_role.name],
            'color': COLORS[device.device_role.name],
            'size': 20,
            'physics': not use_coordinates,
            'font': {
                'color': 'black'
            }
        }
        nodes[id_] = add_coordinates(node, device)
        return id_
    
    def add_prefix(prefix: Prefix) -> str:
        id_ = f'prefix_{prefix.pk}'
        node = {
            'id': f'prefix_{prefix.pk}',
            'netbox_id': prefix.pk,
            'n_edges': 0,
            'name': str(prefix.prefix),
            'type': 'prefix',
            'shape': SHAPES['Prefix'],
            'color': COLORS['Prefix'],
            'size': 5,
            'physics': not use_coordinates,
            'font': {
                'color': 'black'
            }
        }
        nodes[id_] = add_coordinates(node, prefix)
        return id_
    
    def add_edge(vlan: VLAN, point_1_id: str, point_2_id: str):
        edges.append({
            'vid': vlan.vid,
            'name': vlan.name,
            'from': point_1_id,
            'to': point_2_id,
            'color': random_color(vlan.vid),
            'type': 'link'
        })
        nodes[point_1_id]['n_edges'] += 1
        nodes[point_2_id]['n_edges'] += 1
        pass
    vlans = cast(List[VLAN], [ vlan for vlan in VLAN.objects.all() ])
    for vlan in vlans:
        prefixes = cast(List[Prefix], list(Prefix.objects.filter(vlan=vlan).all()))
        if len(prefixes) != 1:
            # WARN: prefixes should have length equal to one
            logger.warn(f'Prefix for vlan ({vlan.vid}) has {len(prefixes)} length')
            continue
        prefix = prefixes[0]
        
        ips = cast(List[IPAddress], list(prefix.get_child_ips().all()))

        devices = [ get_device_ip(ip) for ip in ips ]
        devices = [ device for device in devices if device is not None ]
        devices = [*set(devices)]

        ids = [ add_prefix(prefix) ] + [ add_device(device) for device in devices ]

        ids2 = ids.copy()
        for id1 in ids:
            ids2.remove(id1)
            for id2 in ids2:
                add_edge(vlan, id1, id2)

        if False:
            if prefix.prefix.prefixlen == 30:
                # punto-punto
                if len(ips) != 2:
                    # WARN: ips should have length equal to 2
                    logger.warn(f'Child IPs of "punto-punto" prefix must be of length 2.')
                    continue

                get_device_ip(ips[0])
                get_device_ip(ips[1])

                point_1_type = ips[0].assigned_object_type
                point_2_type = ips[1].assigned_object_type
                if point_1_type is None:
                    logger.warn(f'Point 1 having {ips[0].address} is None.')
                    pass
                if point_2_type is None:
                    logger.warn(f'Point 2 having {ips[0].address} is None.')
                    pass
                if point_1_type is None or point_2_type is None:
                    continue

                point_1 = ips[0].assigned_object
                if point_1_type.model == 'device':
                    point_1 = cast(Device, point_1)
                    point_1_id = add_device(cast(Device, point_1))
                    logger.warn(f'Point 1 is {point_1_type.model} with role {point_1.device_role}.')
                elif point_1_type.model == 'prefix':
                    point_1_id = add_prefix(cast(Prefix, point_1))
                    logger.warn(f'Point 1 type is not device or prefix but {point_1_type.model}.')
                else:
                    logger.warn(f'Point 1 type is not device or prefix but {point_1_type.model}.')
                    continue

                point_2 = ips[0].assigned_object
                if point_2_type.model == 'device':
                    point_2 = cast(Device, point_2)
                    point_2_id = add_device(cast(Device, point_2))
                    logger.warn(f'Point 1 is {point_2_type.model} with role {point_2.device_role}.')
                elif point_2_type.model == 'prefix':
                    point_2_id = add_prefix(cast(Prefix, point_2))
                    logger.warn(f'Point 1 type is not device or prefix but {point_2_type.model}.')
                else:
                    logger.warn(f'Point 1 type is not device or prefix but {point_2_type.model}.')
                    continue
                add_edge(vlan, point_1_id, point_2_id) # type: ignore
            elif prefix and prefix.prefix.prefixlen < 30:
                """
                All'interno della VLAN x è presente il PREFIX y, se y ha più di 2 indirizzi allora
                uno dovrebbe essere il firewall che rappresenterebbe il gateway di quel pool
                """
                ips = cast(List[IPAddress], [ ip for ip in prefix.get_child_ips() ])
                devices = [ cast(Device, ip.assigned_object) for ip in ips if ip.assigned_object_type and  ip.assigned_object_type.model == 'device' ]
                firewalls = [ device for device in devices if device.device_role.name == 'Firewall']
                if len(firewalls) != 1:
                    logger.warn(f'Firewalls inside prefix ({prefix.prefix}) are not one but {len(firewalls)}.')
                    continue
                firewall = firewalls[0]
                
                firewall_id = add_device(firewall)
                prefix_id = add_prefix(prefix)
                edges.append({
                    'vid': vlan.vid,
                    'name': vlan.name,
                    'from': firewall_id,
                    'to': prefix_id,
                    'color': random_color(vlan.vid),
                    'type': 'link'
                })
                pass
            pass # vlan for
        pass
    
    logger.debug(nodes)
    s = '\n'.join([ f"{edge['from']} -> {edge['to']}" for edge in edges ])
    logger.debug(s)

    for node_id in nodes:
        if nodes[node_id]['n_edges'] == 0:
            nodes[node_id]['physics'] = False

    return dict(nodes=nodes, edges=edges)

def create_node(device, save_coords, circuit = None, powerpanel = None, powerfeed= None):

    node = {}
    node_content = ""
    if circuit:
        dev_name = "Circuit " + str(device.cid)
        node["image"] = "../../static/netbox_topology_views/img/circuit.png"
        node["id"] = "c{}".format(device.id)

        if device.provider is not None:
            node_content += "<tr><th>Provider: </th><td>" + device.provider.name + "</td></tr>"
        if device.type is not None:
            node_content += "<tr><th>Type: </th><td>" + device.type.name + "</td></tr>"
    elif powerpanel:
        dev_name = "Power Panel " + str(device.id)
        node["image"] = "../../static/netbox_topology_views/img/power-panel.png"
        node["id"] = "p{}".format(device.id)

        if device.site is not None:
            node_content += "<tr><th>Site: </th><td>" + device.site.name + "</td></tr>"
        if device.location is not None:
            node_content += "<tr><th>Location: </th><td>" + device.location.name + "</td></tr>"
    elif powerfeed:
        dev_name = "Power Feed " + str(device.id)
        node["image"] = "../../static/netbox_topology_views/img/power-feed.png"
        node["id"] = "f{}".format(device.id)

        if device.power_panel is not None:
            node_content += "<tr><th>Power Panel: </th><td>" + device.power_panel.name + "</td></tr>"
        if device.type is not None:
            node_content += "<tr><th>Type: </th><td>" + device.type + "</td></tr>"
        if device.supply is not None:
            node_content += "<tr><th>Supply: </th><td>" + device.supply + "</td></tr>"
        if device.phase is not None:
            node_content += "<tr><th>Phase: </th><td>" + device.phase + "</td></tr>"
        if device.amperage is not None:
            node_content += "<tr><th>Amperage: </th><td>" + str(device.amperage )+ "</td></tr>"
        if device.voltage is not None:
            node_content += "<tr><th>Voltage: </th><td>" + str(device.voltage) + "</td></tr>"
    else:
        dev_name = device.name
        if dev_name is None:
            dev_name = "device name unknown"

        if device.device_type is not None:
            node_content += "<tr><th>Type: </th><td>" + device.device_type.model + "</td></tr>"
        if device.device_role.name is not None:
            node_content +=  "<tr><th>Role: </th><td>" + device.device_role.name + "</td></tr>"
        if device.serial != "":
            node_content += "<tr><th>Serial: </th><td>" + device.serial + "</td></tr>"
        if device.primary_ip is not None:
            node_content += "<tr><th>IP Address: </th><td>" + str(device.primary_ip.address) + "</td></tr>"
        if device.site is not None:
            node_content += "<tr><th>Site: </th><td>" + device.site.name + "</td></tr>"
        if device.location is not None:
            node_content += "<tr><th>Location: </th><td>" + device.location.name + "</td></tr>"
        if device.rack is not None:
            node_content += "<tr><th>Rack: </th><td>" + device.rack.name + "</td></tr>"
        if device.position is not None:
            if device.face is not None:
                node_content += "<tr><th>Position: </th><td> {} ({}) </td></tr>".format(device.position, device.face)
            else:
                node_content += "<tr><th>Position: </th><td>" + device.position + "</td></tr>"

        node["id"] = device.id
        
        if device.device_role.slug in settings.PLUGINS_CONFIG["netbox_topology_views"]["device_img"]:
            node["image"] = "../../static/netbox_topology_views/img/"  + device.device_role.slug + ".png"
        else:
            node["image"] = "../../static/netbox_topology_views/img/role-unknown.png"

        if device.device_role.color != "":
            node["color.border"] = "#" + device.device_role.color
    
    node['untagged_vlan'] = [ i.untagged_vlan.name for i in device.vc_interfaces() if i.untagged_vlan is not None]
    
    dev_title = "<table><tbody> %s</tbody></table>" % (node_content)

    node["title"] = dev_title
    node["name"] = dev_name
    node["label"] = dev_name
    node["shape"] = "image"

    node["physics"] = True        
    if "coordinates" in device.custom_field_data:
        if device.custom_field_data["coordinates"] is not None:
            if ";" in device.custom_field_data["coordinates"]:
                cords =  device.custom_field_data["coordinates"].split(";")
                node["x"] = int(cords[0])
                node["y"] = int(cords[1])
                node["physics"] = False
        else:
            if save_coords:
                node["physics"] = False
            else:
                node["physics"] = True
    return node

def create_edge(edge_id, termination_a, termination_b, circuit = None, cable = None, wireless = None, power=None, type_=''):
    cable_a_name = "device A name unknown" if termination_a["termination_name"] is None else termination_a["termination_name"]
    cable_a_dev_name = "device A name unknown" if termination_a["termination_device_name"] is None else termination_a["termination_device_name"]
    cable_b_name= "device A name unknown" if termination_b["termination_name"] is None else termination_b["termination_name"]
    cable_b_dev_name  = "cable B name unknown" if termination_b["termination_device_name"] is None else termination_b["termination_device_name"]

    edge = {}
    edge["id"] = edge_id
    edge["from"] = termination_a["device_id"]
    edge["to"] = termination_b["device_id"]
    edge["type"] = type_

    if circuit is not None:
        edge["dashes"] = True
        edge["title"] = "Circuit provider: "  + circuit["provider_name"] + "<br>"
        edge["title"] += "Termination between <br>"
        edge["title"] += cable_b_dev_name + " [" + cable_b_name +  "]<br>"
        edge["title"] += cable_a_dev_name + " [" + cable_a_name +  "]"
    elif wireless is not None:
        edge["dashes"] = [2, 10, 2, 10]
        edge["title"] = "Wireless Connection between <br> " + cable_a_dev_name + " [" + cable_a_name +  "]<br>" + cable_b_dev_name + " [" + cable_b_name + "]"
    elif power is not None:
        edge["dashes"] = [5, 5, 3, 3] 
        edge["title"] = "Power Connection between <br> " + cable_a_dev_name + " [" + cable_a_name +  "]<br>" + cable_b_dev_name + " [" + cable_b_name + "]"
    else:
        edge["title"] = "Cable between <br> " + cable_a_dev_name + " [" + cable_a_name +  "]<br>" + cable_b_dev_name + " [" + cable_b_name + "]"
    
    if cable is not None and cable.color != "":
        edge["color"] = "#" + cable.color
    
    return edge

def create_circuit_termination(termination):
    if isinstance(termination, CircuitTermination):
        return { "termination_name": termination.circuit.provider.name, "termination_device_name": termination.circuit.cid, "device_id": "c{}".format(termination.circuit.id) }
    if isinstance(termination, Interface) or isinstance(termination, FrontPort) or isinstance(termination, RearPort):
        return { "termination_name": termination.name, "termination_device_name": termination.device.name, "device_id": termination.device.id }
    return None

def get_topology_data(queryset, hide_unconnected, save_coords, use_coordinates, show_circuit, show_power):
    nodes_devices = {}
    edges = []
    nodes = []
    edge_ids = 0
    nodes_circuits = {}
    nodes_powerpanel = {}
    nodes_powerfeed = {}
    nodes_provider_networks = {}
    cable_ids = {}
    if not queryset:
        return None

    ignore_cable_type = settings.PLUGINS_CONFIG["netbox_topology_views"]["ignore_cable_type"]

    device_ids = [d.id for d in queryset]
    site_ids = [d.site.id for d in queryset]

    if show_circuit:
        circuits = CircuitTermination.objects.filter( Q(site_id__in=site_ids) | Q( provider_network__isnull=False) ).prefetch_related("provider_network", "circuit")
        for circuit in circuits:
            if not hide_unconnected and circuit.circuit.id not in nodes_circuits:
                nodes_circuits[circuit.circuit.id] = circuit.circuit

            termination_a = {}
            termination_b = {}
            circuit_model = {}
            if circuit.cable is not None:
                termination_a = create_circuit_termination(circuit.cable.a_terminations[0])
                termination_b = create_circuit_termination(circuit.cable.b_terminations[0])
            elif circuit.provider_network is not None:
                if circuit.provider_network.id not in nodes_provider_networks:
                    nodes_provider_networks[circuit.provider_network.id] = circuit.provider_network

            if bool(termination_a) and bool(termination_b):
                circuit_model = {"provider_name": circuit.circuit.provider.name}
                edge_ids += 1
                edges.append(create_edge(edge_id=edge_ids,circuit=circuit_model, termination_a=termination_a, termination_b=termination_b, type_='circuit'))

                circuit_has_connections = False
                for termination in [circuit.cable.a_terminations[0], circuit.cable.b_terminations[0]]:
                    if not isinstance(termination, CircuitTermination):
                        if termination.device.id not in nodes_devices and termination.device.id in device_ids:
                            nodes_devices[termination.device.id] = termination.device
                            circuit_has_connections = True
                        else:
                            if termination.device.id in device_ids:
                                 circuit_has_connections = True
      
                if circuit_has_connections and hide_unconnected:
                    if circuit.circuit.id not in nodes_circuits:
                        nodes_circuits[circuit.circuit.id] = circuit.circuit


        for d in nodes_circuits.values():
            nodes.append(create_node(d, save_coords, circuit=True))

    links = CableTermination.objects.filter( Q(_device_id__in=device_ids) ).select_related("termination_type")
    wlan_links = WirelessLink.objects.filter( Q(_interface_a_device_id__in=device_ids) & Q(_interface_b_device_id__in=device_ids))
    
    
    if show_power:
        power_panels = PowerPanel.objects.filter( Q (site_id__in=site_ids))
        power_panels_ids = [d.id for d in power_panels]
        power_feeds = PowerFeed.objects.filter( Q (power_panel_id__in=power_panels_ids))
        
        for power_feed in power_feeds:
            if not hide_unconnected  or (hide_unconnected and power_feed.cable_id is not None):
                if power_feed.power_panel.id not in nodes_powerpanel:
                    nodes_powerpanel[power_feed.power_panel.id] = power_feed.power_panel

                power_link_name = ""
                if power_feed.id not in nodes_powerfeed:
                    if hide_unconnected:
                        if power_feed.link_peers[0].device.id in device_ids:
                            nodes_powerfeed[power_feed.id] = power_feed
                            power_link_name =power_feed.link_peers[0].name
                    else:
                        nodes_powerfeed[power_feed.id] = power_feed

                edge_ids += 1
                termination_a = { "termination_name": power_feed.power_panel.name, "termination_device_name": "", "device_id": "p{}".format(power_feed.power_panel.id) }
                termination_b = { "termination_name": power_feed.name, "termination_device_name": power_link_name, "device_id": "f{}".format(power_feed.id) }
                edges.append(create_edge(edge_id=edge_ids, termination_a=termination_a, termination_b=termination_b, power=True, type_='power'))

                if power_feed.cable_id is not None:
                    if power_feed.cable.id not in cable_ids:
                        cable_ids[power_feed.cable.id] = {}
                    cable_ids[power_feed.cable.id][power_feed.cable_end] = termination_b
                
        
        for d in nodes_powerfeed.values():
            nodes.append(create_node(d, save_coords, powerfeed = True))
        
        for d in nodes_powerpanel.values():
            nodes.append(create_node(d, save_coords, powerpanel = True))        

    for link in links:
        if link.termination_type.name in ignore_cable_type :
            continue
        
        #Normal device cables
        if link.termination_type.name in supported_termination_types:
            complete_link = False
            if link.cable_end == "A":
                if link.cable.id not in cable_ids:
                    cable_ids[link.cable.id] = {}
                else:
                    if 'B' in cable_ids[link.cable.id]:
                        if cable_ids[link.cable.id]['B'] is not None:
                            complete_link = True
            elif link.cable_end == "B":
                if link.cable.id not in cable_ids:
                    cable_ids[link.cable.id] = {}
                else:
                    if 'A' in cable_ids[link.cable.id]:
                        if cable_ids[link.cable.id]['A'] is not None:
                            complete_link = True
            else:
                print("Unkown cable end")
            cable_ids[link.cable.id][link.cable_end] = link

            if complete_link:
                edge_ids += 1
                if isinstance(cable_ids[link.cable.id]["B"], CableTermination):
                    if cable_ids[link.cable.id]["B"]._device_id not in nodes_devices:
                        nodes_devices[cable_ids[link.cable.id]["B"]._device_id] = cable_ids[link.cable.id]["B"].termination.device
                    termination_b = { "termination_name": cable_ids[link.cable.id]["B"].termination.name, "termination_device_name": cable_ids[link.cable.id]["B"].termination.device.name, "device_id": cable_ids[link.cable.id]["B"].termination.device.id }
                else:
                    termination_b = cable_ids[link.cable.id]["B"]

                if isinstance(cable_ids[link.cable.id]["A"], CableTermination):
                    if cable_ids[link.cable.id]["A"]._device_id not in nodes_devices:
                        nodes_devices[cable_ids[link.cable.id]["A"]._device_id] = cable_ids[link.cable.id]["A"].termination.device
                    termination_a = { "termination_name": cable_ids[link.cable.id]["A"].termination.name, "termination_device_name": cable_ids[link.cable.id]["A"].termination.device.name, "device_id": cable_ids[link.cable.id]["A"].termination.device.id }
                else:
                    termination_a = cable_ids[link.cable.id]["A"]
               
                edges.append(create_edge(edge_id=edge_ids, cable=link.cable, termination_a=termination_a, termination_b=termination_b, type_='link'))

    for wlan_link in wlan_links:
        if wlan_link.interface_a.device.id not in nodes_devices:
                nodes_devices[wlan_link.interface_a.device.id] = wlan_link.interface_a.device
        if wlan_link.interface_b.device.id not in nodes_devices:
                nodes_devices[wlan_link.interface_b.device.id] = wlan_link.interface_b.device
        
        termination_a = {"termination_name": wlan_link.interface_a.name, "termination_device_name": wlan_link.interface_a.device.name, "device_id": wlan_link.interface_a.device.id}
        termination_b = {"termination_name": wlan_link.interface_b.name, "termination_device_name": wlan_link.interface_b.device.name, "device_id": wlan_link.interface_b.device.id}
        wireless = {"ssid": wlan_link.ssid }

        edge_ids += 1
        edges.append(create_edge(edge_id=edge_ids, termination_a=termination_a, termination_b=termination_b,wireless=wireless, type_='wlan'))

    for qs_device in queryset:
        if qs_device.id not in nodes_devices and not hide_unconnected:
            nodes_devices[qs_device.id] = qs_device

    results = {}
    
    for d in nodes_devices.values():
        nodes.append(create_node(d, save_coords))

    results["nodes"] = nodes 
    results["edges"] = edges
    return results

def get_routers_and_firewall(topo_data, use_coordinates):
    if topo_data is None:
        topo_data = {}

    data = nodes(use_coordinates)

    topo_data['nodes2'] = [ data['nodes'][id_] for id_ in data['nodes'] ]
    topo_data['edges2'] = data['edges']

    pass


class TopologyHomeView(PermissionRequiredMixin, View):
    permission_required = ("dcim.view_site", "dcim.view_device")

    """
    Show the home page
    """
    def get(self, request):
        self.filterset = DeviceFilterSet
        self.queryset = Device.objects.all().select_related("device_type", "device_role")
        self.queryset = self.filterset(request.GET, self.queryset).qs
        topo_data = None
        use_coordinates = True

        if request.GET:
            save_coords = False
            if 'save_coords' in request.GET:
                if request.GET["save_coords"] == "on":
                    save_coords = True

            use_coordinates = False
            if 'use_coordinates' in request.GET:
                if request.GET["use_coordinates"] == "on":
                    use_coordinates = True
                    
            hide_unconnected = False
            if "hide_unconnected" in request.GET:
                if request.GET["hide_unconnected"] == "on" :
                    hide_unconnected = True

            show_power = False
            if "show_power" in request.GET:
                if request.GET["show_power"] == "on" :
                    show_power = True

            show_circuit = False
            if "show_circuit" in request.GET:
                if request.GET["show_circuit"] == "on" :
                    show_circuit = True

            if "draw_init" in request.GET:
                if request.GET["draw_init"].lower() == "true":
                    topo_data = get_topology_data(self.queryset, hide_unconnected, save_coords, show_circuit, show_power)
            else:
                topo_data = get_topology_data(self.queryset, hide_unconnected, save_coords, use_coordinates,  show_circuit, show_power)
        else:
            preselected_device_roles = settings.PLUGINS_CONFIG["netbox_topology_views"]["preselected_device_roles"]
            preselected_tags = settings.PLUGINS_CONFIG["netbox_topology_views"]["preselected_tags"]
            always_save_coordinates = bool(settings.PLUGINS_CONFIG["netbox_topology_views"]["always_save_coordinates"])

            q_device_role_id = DeviceRole.objects.filter(name__in=preselected_device_roles).values_list("id", flat=True)
            q_tags = Tag.objects.filter(name__in=preselected_tags).values_list("name", flat=True)

            q = QueryDict(mutable=True)
            q.setlist("device_role_id", list(q_device_role_id))
            q.setlist("tag", list(q_tags))
            q["draw_init"] = settings.PLUGINS_CONFIG["netbox_topology_views"]["draw_default_layout"]
            if always_save_coordinates:
                q["save_coords"] = "on"
            query_string = q.urlencode()
            return HttpResponseRedirect(request.path + "?" + query_string)

        get_routers_and_firewall(topo_data, use_coordinates)

        return render(request, "netbox_topology_views/index.html" , {
                "filter_form": DeviceFilterForm(request.GET, label_suffix=""),
                "topology_data": json.dumps(topo_data),
                'use_coordinates': json.dumps(use_coordinates)
            }
        )
