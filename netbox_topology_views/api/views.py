from rest_framework.viewsets import ModelViewSet, ViewSet, ReadOnlyModelViewSet, GenericViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from rest_framework.routers import APIRootView

from .serializers import TopologyDummySerializer
from django.conf import settings

from dcim.models import  DeviceRole, Device, Cable , PowerPanel,  PowerFeed
from ipam.models import Prefix
from circuits.models import Circuit
from extras.models import Tag

from typing import cast, Union

class TopologyViewsRootView(APIRootView):
    def get_view_name(self):
        return 'TopologyViews'

class SaveCoordsViewSet(ReadOnlyModelViewSet):
    queryset = Device.objects.all()
    serializer_class = TopologyDummySerializer

    @action(detail=False, methods=['patch'])
    def save_coords(self, request):
        results = {}
        if settings.PLUGINS_CONFIG["netbox_topology_views"]["allow_coordinates_saving"]:
            device_id = None
            x_coord = None
            y_coord = None
            if not ("netbox_id" in request.data and "x" in request.data and "y" in request.data):
                request.data['status'] = 'netbox_id,x or y undefined'
                return Response(request.data, status=500)
            
            netbox_id = request.data["netbox_id"]
            x_coord = request.data["x"]
            y_coord = request.data["y"]
            
            if request.data['type'] == 'device':
                actual_device= Device.objects.get(pk=netbox_id)
            elif request.data['type'] == 'prefix':
                actual_device= Prefix.objects.get(pk=netbox_id)
            else:
                request.data['status'] = 'Unknown type'
                return Response(request.data, status=500)
            
            actual_device = cast(Union[Device, Prefix], actual_device)

            if "coordinates" in actual_device.custom_field_data:
                actual_device.custom_field_data["coordinates"] = "%s;%s" % (x_coord,y_coord)
                actual_device.save()
                results["status"] = "saved coords"
            else:
                try:
                    actual_device.custom_field_data["coordinates"] = "%s;%s" % (x_coord,y_coord)
                    actual_device.save()
                    results["status"] = "saved coords"
                except :
                    results["status"] = "coords custom field not created"
                    return Response(status=500)

            return Response(results)
        else:
            results["status"] = "not allowed to save coords"
            return Response(results, status=500)

