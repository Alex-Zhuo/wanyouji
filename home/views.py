from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from rest_framework.response import Response


class DetailPKtoNoViewSet(viewsets.ModelViewSet):
    lookup_field = 'no'
    lookup_url_kwarg = 'pk'


class ReturnNoDetailViewSet(viewsets.ModelViewSet):
    def retrieve(self, request, *args, **kwargs):
        from django.http import Http404
        raise Http404


class ReturnNoneViewSet(ReturnNoDetailViewSet):

    def list(self, request, *args, **kwargs):
        return Response()
