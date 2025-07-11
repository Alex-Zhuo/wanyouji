# coding: utf-8
from __future__ import unicode_literals

from django.apps import AppConfig


class MallConfig(AppConfig):
    name = 'mall'
    verbose_name = '用户管理'

    def ready(self):
        from user_agents import parsers
        parsers.MOBILE_BROWSER_FAMILIES = parsers.MOBILE_BROWSER_FAMILIES + ('Chrome Mobile',)

