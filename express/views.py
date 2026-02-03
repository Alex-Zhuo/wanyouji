from django.shortcuts import render

# Create your views here.
from express.models import Division
import json
from express.serializers import CitySerializer
from rest_framework.response import Response

from home.views import ReturnNoDetailViewSet


class CityViewSet(ReturnNoDetailViewSet):
    queryset = Division.objects.filter(is_use=True)
    serializer_class = CitySerializer
    permission_classes = []
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        from caches import get_redis, city_key
        redis = get_redis()
        data = redis.get(city_key)
        if not data:
            qs = self.queryset.filter(type=Division.TYPE_CITY, city__isnull=False, county__isnull=True)
            data = self.serializer_class(qs, many=True).data
            redis.set(city_key, json.dumps(data))
        else:
            data = json.loads(data)
        return Response(data)
