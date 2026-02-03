from django.db import models

from mp.models import SystemMP


class Home(SystemMP):
    class Meta:
        verbose_name_plural = verbose_name = '数据统计'
        proxy = True
