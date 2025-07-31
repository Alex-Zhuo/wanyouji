# coding: utf-8
from __future__ import unicode_literals

import logging
from rest_framework import serializers
from django.utils import timezone
from restframework_ext.exceptions import CustomAPIException
from caiyicloud.models import CyTicketPack, CyTicketType

log = logging.getLogger(__name__)


class CyTicketPackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CyTicketPack
        fields = ['cy_no', 'ticket_type_id', 'price', 'qty']


class CySeatUrlSerializer(serializers.ModelSerializer):
    no = serializers.CharField(required=True)
    navigate_url = serializers.CharField(required=True)

    def create(self, validated_data):
        try:
            cf = CyTicketType.objects.get(cy_no=validated_data['no'])
        except CyTicketType.DoesNotExist:
            raise CustomAPIException('票档no错误')
        ret = cf.cy_session.get_seat_url(validated_data['no'], validated_data['navigate_url'])
        return ret

    class Meta:
        model = CyTicketType
        fields = ['no', 'navigate_url']


class CySeatInfoSerializer(serializers.ModelSerializer):
    biz_id = serializers.CharField(required=True)

    def create(self, validated_data):
        ret = CyTicketType.get_seat_info(biz_id=validated_data['biz_id'])
        return ret

    class Meta:
        model = CyTicketType
        fields = ['biz_id']
