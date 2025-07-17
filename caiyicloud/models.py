# coding: utf-8
from __future__ import unicode_literals
from django.db import models
from datetime import timedelta
from django.conf import settings
import logging
from random import sample
from mall.models import User
from common.utils import get_config
from django.core.exceptions import ValidationError
from django.utils import timezone
from restframework_ext.exceptions import CustomAPIException
import json
from typing import List, Dict
from django.db.transaction import atomic

from ticket.models import ShowProject

log = logging.getLogger(__name__)


class CaiYiCloudApp(models.Model):
    name = models.CharField('名称', max_length=50)
    app_id = models.CharField('app_id', max_length=50)
    supplier_id = models.CharField('supplierId', max_length=64)
    private_key = models.TextField('私钥')

    class Meta:
        verbose_name_plural = verbose_name = '彩艺云配置'

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        return cls.objects.first()

class CyShowEvent(models.Model):
    show = models.OneToOneField(ShowProject, verbose_name='项目', on_delete=models.CASCADE, related_name='cy_event')

    class Meta:
        verbose_name_plural = verbose_name = '彩艺云节目'

    def __str__(self):
        return self.name