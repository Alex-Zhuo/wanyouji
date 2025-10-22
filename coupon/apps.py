# coding=utf-8
from __future__ import unicode_literals

from django.apps import AppConfig


class CouponConfig(AppConfig):
    name = 'coupon'
    verbose_name = '消费券管理'

    def ready(self):
        from coupon import signals
