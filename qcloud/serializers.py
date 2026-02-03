# coding: utf-8
from __future__ import unicode_literals

from rest_framework.exceptions import ValidationError
from rest_framework.serializers import CharField

from restframework_ext.exceptions import CustomAPIException
from .consts import VrKeys, VrSessionUtils


class VerificationCodeMixin(object):
    mobile = CharField(write_only=True, label='手机', min_length=8, max_length=20)
    vr = CharField(write_only=True)

    vrcode_key = None

    def validate_mobile(self, value):
        req = self.context.get('request')
        if not self.vrcode_key:
            raise ValidationError('内部错误: vr001')
        if not value == req.session.get(VrKeys.get_mobile(self.vrcode_key)):
            raise ValidationError('验证码错误')
        return value

    def validate_vr(self, value):
        req = self.context['request']
        if VrSessionUtils.has_valid(req, self.vrcode_key, True):
            if value == req.session.get(self.vrcode_key):
                return value
            else:
                raise CustomAPIException(u'验证码过期或错误')
        else:
            raise CustomAPIException(u'验证码过期或错误')