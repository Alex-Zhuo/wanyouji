from django.shortcuts import render

# Create your views here.
from home.views import ReturnNoDetailViewSet
from renovation.models import OpenScreenMedia
from renovation.serializers import OpenScreenMediaSerializer


class OpenScreenMediaSet(ReturnNoDetailViewSet):
    queryset = OpenScreenMedia.objects.filter(is_use=True)
    serializer_class = OpenScreenMediaSerializer
    permission_classes = []
    http_method_names = ['get']
