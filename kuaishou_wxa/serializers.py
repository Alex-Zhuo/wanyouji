# -*- coding: utf-8 -*-

from rest_framework import serializers
from django.db.transaction import atomic
from mall.serializers import Stricth5UserRegisterSerializer
from kuaishou_wxa.models import KsUser
from restframework_ext.exceptions import CustomAPIException


class UserKsSetMobileSerializer(Stricth5UserRegisterSerializer):
    first_name = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        self.validate_request(validated_data)
        user = request.user
        from rest_framework.response import Response
        resp = Response()
        return KsUser.check_user_ks(validated_data['mobile'], validated_data.get('first_name'), request, resp, user)

    class Meta:
        model = KsUser
        fields = ['mobile', 'vr', 'imgrand', 'reqid', 'first_name']
