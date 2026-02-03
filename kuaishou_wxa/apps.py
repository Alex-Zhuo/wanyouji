# coding=utf-8
from __future__ import unicode_literals

from django.apps import AppConfig


class KShouWxaConfig(AppConfig):
    name = 'kuaishou_wxa'
    verbose_name = '快手管理'

    def ready(self):
        from kuaishou_wxa import signals
