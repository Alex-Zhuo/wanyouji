# coding:utf-8
from __future__ import unicode_literals

import os

import yaml

_CONF = None


def get_config():
    global _CONF
    if not _CONF:
        from django.conf import settings
        _CONF = yaml.safe_load(open(os.path.join(settings.BASE_DIR, 'env.yml'), 'r', encoding='UTF-8'))
    return _CONF


class ConfigInst:
    def __init__(self):
        pass

    @property
    def default_pay_type(self):
        pay = get_config().get('pay')
        if pay:
            return pay.get('default_pay_type')


ConfigInst = ConfigInst()

FILE_FIELD_PREFIX = 'files'
IMAGE_FIELD_PREFIX = 'images'
VIDEO_EXT_LIST = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'mpeg', 'mpg']
