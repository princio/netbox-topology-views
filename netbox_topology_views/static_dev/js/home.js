import { DataSet } from "vis-data/esnext";
import { Network } from "vis-network/esnext";
//import 'vis-util';

let physics_enabled = true;
var graph = null;
var container = null;
var downloadButton = null;
var fitButton = null;
var physicsButton = null;
var clusterButton = null;
const MIME_TYPE = "image/png";
var canvas = null;
var csrftoken = null;
var nodes = new DataSet();
var edges = new DataSet();
const physics = {
    enabled: physics_enabled,
    stabilization: {
        enabled: true,
    },
    maxVelocity: 20,
    barnesHut: {
    //     centralGravity: 0.6,
        gravitationalConstant: -2000,
    //     springLength: 50, // 95
    //     springConstant: 0.02, // 0.04
    //     avoidOverlap: 1
    },
    solver: 'barnesHut',
};
var options = {
    interaction: {
        hover: true,
        hoverConnectedEdges: true,
        multiselect: true
    },
    nodes: {
        shape: 'image',
        brokenImage: '../../static/netbox_topology_views/img/role-unknown.png',
        size: 35,
        font: {
            multi: 'md',
            face: 'helvetica',
        },
    },
    edges: {
        length: 50,
        width: 2,
        font: {
            face: 'helvetica',
        },
    },
    physics: physics
};
var coord_save_checkbox = null;
var htmlElement = null;

export function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};


export function htmlTitle(html) {
    container = document.createElement("div");
    container.innerHTML = html;
    return container;
};

export function addEdge(item) {
    item.title = htmlTitle(item.name);
    item.shadow = { enabled: false };
    item.label = `${item.vid}`;
    edges.add(item);
};

export function addNode(node, opt) {
    const item = JSON.parse(JSON.stringify(node));
    item.title = htmlTitle(item.name);
    if (opt && opt.small) {
        if (item.type === 'prefix') {
            item.color = 'black';
            item.label = undefined;
            item.size = 5;
        }
    }
    nodes.update(item);
}

export function smallNode(graph, node) {
    graph.updateClusteredNode(node.id, {
        color: 'black',
        label: undefined,
        size: 5
    })
}

export function iniPlotboxIndex() {
    csrftoken = getCookie('csrftoken');
    container = document.getElementById('visgraph');
    htmlElement = document.getElementsByTagName("html")[0];
    downloadButton = document.getElementById('btnDownloadImage');
    physicsButton = document.getElementById('btnPhysics');
    fitButton = document.getElementById('btnFit');
    cooButton = document.getElementById('btnCoo');
    clusterButton = document.getElementById('btnCluster');
    handleLoadData();
    btnFullView = document.getElementById('btnFullView');
    coord_save_checkbox = document.getElementById('id_save_coords');
};

export function performGraphDownload() {
    var tempDownloadLink = document.createElement('a');
    var generatedImageUrl = canvas.toDataURL(MIME_TYPE);

    tempDownloadLink.href = generatedImageUrl;
    tempDownloadLink.download = "topology";
    document.body.appendChild(tempDownloadLink);
    tempDownloadLink.click();
    document.body.removeChild(tempDownloadLink);
};

const saveCoord = async (data) => {
    return new Promise((resolve) => {
        var url = "/api/plugins/netbox_topology_views/save-coords/save_coords/";
        var xhr = new XMLHttpRequest();
        xhr.open("PATCH", url);
        xhr.setRequestHeader('X-CSRFToken', csrftoken );
        xhr.setRequestHeader("Accept", "application/json");
        xhr.setRequestHeader("Content-Type", "application/json");

        xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            console.log(xhr.status);
            resolve(xhr.status);
        }};

        xhr.send(JSON.stringify(data));
    });
}

export function handleLoadData() {
    if (topology_data !== null) {
        
        if (htmlElement.dataset.netboxColorMode == "dark") {
            options.nodes.font.color = "#fff";
        }

        graph = null;
        nodes = new DataSet();
        edges = new DataSet();

        graph = new Network(container, { nodes: nodes, edges: edges }, options);
        
        // topology_data.edges.forEach(addEdge);
        // topology_data.nodes.forEach(addNode);
        // topology_data.devices.routers.forEach(addNode);
        // topology_data.devices.firewalls.forEach(addNode);
        // topology_data.devices_all.forEach(addNode);
        // topology_data.vlan_edges.forEach(addEdge);

        topology_data.nodes2.forEach((n) => addNode(n, undefined));
        topology_data.edges2.forEach(addEdge);

        graph.fit();
        canvas = document.getElementById('visgraph').getElementsByTagName('canvas')[0];

        downloadButton.onclick = function(e) { performGraphDownload(); return false; };
        
        fitButton.onclick = function(e) {
            graph.setOptions({ physics: false });
            // topology_data.nodes2.forEach((n) => smallNode(graph, n));
            // graph.redraw();
            graph.fit({ animation: false });
            graph.setOptions({ physics: true });
            return false;
        };
        
        cooButton.onclick = function(e) {
            reqs = topology_data.nodes2.map((n) => ({...n, ...graph.getPosition(n.id)}))
            console.log(reqs);
            reqs.forEach(async (req) => await saveCoord(req));
            return false;
        };
        
        physicsButton.onclick = function(e) {
            if( physicsButton.dataset.on == 'true') {
                graph.setOptions({ physics: false });
                physicsButton.dataset.on = 'false';
                physicsButton.setHTML('Physics is Off');
                physics_enabled = false;
                nodes.forEach((n) => { n.physics = false });
            }
            else {
                nodes.forEach((n) => { n.physics = true });
                graph.setData({ nodes, edges });
                graph.setOptions({ physics: true });
                physicsButton.dataset.on = 'true'
                physicsButton.setHTML('Physics is On')
                physics_enabled = true;
            }

            return false;
        };
        
        clusterButton.onclick = function(e) {
            nodes.forEach((node) => {
                if (node.type !== 'device') return;
                const prefixes = nodes.map((n2) => n2, { filter: (n2) => n2.cluster && n2.cluster === node.id });
                const edges2 = [];
                for (const pr of prefixes) {
                    edges2.push(edges.map((edge) => `${edge.vid}`, { filter: (e) => e.from === pr.id || e.to === pr.id }));
                }
                console.log(edges2);
                graph.cluster({
                    joinCondition: (parentNodeOptions) => {
                        const toCluster = parentNodeOptions.cluster && parentNodeOptions.cluster === node.id;
                        return toCluster;
                    },
                    clusterNodeProperties: {
                        id: "cidCluster_" + node.id,
                        borderWidth: 3,
                        shape: "database",
                        title: htmlTitle(prefixes.map((n2) => n2.name).join('<br/>'))
                    },
                    clusterEdgeProperties: {
                        id: "cidClusterEdge_" + node.id,
                        label: `#${edges2.length}`,
                        title: htmlTitle(edges2.join('<br/>'))
                    },
                })
            });
            
            const prefixes = nodes.map((n2) => n2.name, { filter: (n2) => n2.type === 'prefix' && n2.n_edges === 0 });
            graph.cluster({
                joinCondition: (parentNodeOptions) => {
                    return parentNodeOptions.type === 'prefix' && parentNodeOptions.n_edges === 0;
                },
                clusterNodeProperties: {
                    id: "cidCluster_orphans",
                    borderWidth: 3,
                    color: 'pink',
                    label: 'orphans',
                    shape: "database",
                    title: htmlTitle(prefixes.join('<br/>'))
                },
            });
        }

        graph.on("dragStart", function (params) {
            for (const edge of params.edges) {
                graph.updateEdge(edge, { smooth: false });
            }
            if (physics_enabled) {
                
                graph.setOptions({
                    physics: {
                        enabled: false
                    }
                })
            }
        })

        graph.on("dragEnd", function (params) {
            dragged = this.getPositions(params.nodes);

            if (coord_save_checkbox.checked) {
                if (Object.keys(dragged).length !== 0) {
                    for (dragged_id in dragged) {
                        const node = topology_data.nodes2.filter((n) => n.id === dragged_id)[0]

                        var url = "/api/plugins/netbox_topology_views/save-coords/save_coords/";
                        var xhr = new XMLHttpRequest();
                        xhr.open("PATCH", url);
                        xhr.setRequestHeader('X-CSRFToken', csrftoken );
                        xhr.setRequestHeader("Accept", "application/json");
                        xhr.setRequestHeader("Content-Type", "application/json");
    
                        xhr.onreadystatechange = function () {
                        if (xhr.readyState === 4) {
                            console.log(xhr.status);
                        }};

                        const data = JSON.stringify({
                            ...node,
                            x: dragged[dragged_id].x,
                            y: dragged[dragged_id].y
                        });
    
                        xhr.send(data);
                    }
                }
            }

            if (physics_enabled) {
                graph.setOptions({
                    physics: {
                        enabled: true
                    }
                })
            }
        });

        graph.on("doubleClick", function (params) {
            
            if (params.nodes.length == 1) {
                if (graph.isCluster(params.nodes[0]) == true) {
                  graph.openCluster(params.nodes[0]);
                }
                return;
              }
            let selected_devices = params.nodes;
            for (let selected_device in selected_devices) {
                let url = ""
                if(String(selected_devices[selected_device]).startsWith("c")) {
                    cid = selected_devices[selected_device].substring(1);
                    url = "/circuits/circuits/" + cid + "/";
                }
                else if (String(selected_devices[selected_device]).startsWith("p")) {
                    cid = selected_devices[selected_device].substring(1);
                    url = "/dcim/power-panels/" + cid + "/";
                }
                else if (String(selected_devices[selected_device]).startsWith("f")) {
                    cid = selected_devices[selected_device].substring(1);
                    url = "/dcim/power-feeds/" + cid + "/";
                }
                else {
                    url = "/dcim/devices/" + selected_devices[selected_device] + "/";
                }
                
                window.open(url, "_blank");
            }

        });
    }
};

export function load_doc() {
    if (document.readyState !== 'loading') {
        iniPlotboxIndex();
      } else {
        document.addEventListener('DOMContentLoaded', iniPlotboxIndex);
    }
};


load_doc();
