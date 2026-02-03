# coding: utf-8# coding: utf-8

from __future__ import unicode_literals

from django.apps import AppConfig


class ShoppingPointsConfig(AppConfig):
    name = 'shopping_points'
    verbose_name = '代理管理'

    def ready(self):
        from shopping_points import signals
