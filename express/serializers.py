# -*- coding: utf-8 -*-

from express.models import Division
from rest_framework import serializers


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = ['id', 'city']
