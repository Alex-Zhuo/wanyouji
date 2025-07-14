# coding: utf-8
from __future__ import unicode_literals
from rest_framework import serializers

from renovation.models import OpenScreenMedia


class OpenScreenMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpenScreenMedia
        fields = ['image', 'video', 'seconds']
