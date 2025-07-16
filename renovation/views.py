from django.shortcuts import render

# Create your views here.
from home.views import ReturnNoDetailViewSet
from renovation.models import OpenScreenMedia
from renovation.serializers import OpenScreenMediaSerializer
from rest_framework.response import Response


class OpenScreenMediaViewSet(ReturnNoDetailViewSet):
    queryset = OpenScreenMedia.objects.filter(is_use=True)
    serializer_class = OpenScreenMediaSerializer
    permission_classes = []
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        code = request.GET.get('code')
        obj = self.queryset.filter(code=code).first()
        return Response(self.serializer_class(obj, context={'request': request}).data)
