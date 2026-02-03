# coding: utf-8
from __future__ import unicode_literals

import re

import time
from rest_framework.exceptions import ValidationError

from restframework_ext.permissions import IsPermittedUser


class BindPermission(IsPermittedUser):
    def has_permission(self, request, view):
        if super(BindPermission, self).has_permission(request, view):
            if request.user.is_binding_mobile:
                raise ValidationError('您已绑定过, 请勿重复绑定')
        return True


class VrKeys(object):
    bind = 'bind'
    vr = 'vr'
    agentapply = 'agentapply'
    keys = [vr, bind, agentapply]
    vr_keys_perms = {bind: [BindPermission()]}

    @classmethod
    def get_mobile(cls, key, raise_exception=True):
        if key in cls.keys:
            return '%s_mobile' % key
        if raise_exception:
            raise TypeError(key)

    @classmethod
    def get_expire_at(cls, key, raise_exception=True):
        if key in cls.keys:
            return '%s_expire_at' % key
        if raise_exception:
            raise TypeError(key)

    @classmethod
    def register(cls, key, perms=None):
        if not hasattr(cls, key):
            setattr(cls, key, key)
            cls.keys.append(key)
            if perms:
                cls.vr_keys_perms[key] = perms
        else:
            raise ValueError('key: %s conflicts, please check' % key)


class Regex(object):
    mobile = re.compile(r'\d{8,11}')


class VrSessionUtils(object):
    @classmethod
    def set_code(cls, session, key, mobile, code, expired_at=None):
        session[VrKeys.get_mobile(key)] = mobile
        session[key] = code
        # set 120 expiration. after register ok, delete this session and new
        session[VrKeys.get_expire_at(key)] = expired_at or int(time.time()) + 120

    @classmethod
    def clear_code(cls, session, key):
        session.pop(VrKeys.get_mobile(key), None)
        session.pop(key, None)
        session.pop(VrKeys.get_expire_at(key), None)

    @classmethod
    def has_valid(cls, request, key, auto_clear=False):
        if request.session.get(key, None):
            expire_at = request.session.get('%s_expire_at' % key)
            expired = time.time() >= expire_at
            if expired:
                if auto_clear:
                    cls.clear_code(request.session, key)
                return False
            else:
                return True
        else:
            return False
