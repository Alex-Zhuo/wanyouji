# coding=utf-8
from __future__ import unicode_literals

from django.apps import AppConfig


class XiaoHongShuConfig(AppConfig):
    name = 'xiaohongshu'
    verbose_name = '小红书管理'

    def ready(self):
        from xiaohongshu import signals
