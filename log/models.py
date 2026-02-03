# coding=utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.admin.models import LogEntry


class LogEntryMy(LogEntry):
    class Meta:
        verbose_name = verbose_name_plural = '操作日志'
        proxy = True

# Create your models here.
