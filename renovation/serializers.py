# coding: utf-8
from __future__ import unicode_literals
from rest_framework import serializers

from renovation.models import OpenScreenMedia, MediaType


class MediaTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaType
        fields = ['code', 'name']


class OpenScreenMediaSerializer(serializers.ModelSerializer):
    media_type = MediaTypeSerializer()

    class Meta:
        model = OpenScreenMedia
        fields = ['image', 'video', 'seconds', 'media_type']
