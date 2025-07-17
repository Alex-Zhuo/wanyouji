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

from ticket.models import ShowProject, ShowType

log = logging.getLogger(__name__)
# -*- coding: utf-8 -*-
"""
节目分类字典
"""
EVENT_CATEGORIES = {
    17: "演唱会", 18: "音乐节", 19: "Livehouse", 20: "话剧", 21: "歌剧", 22: "音乐剧",
    23: "音乐会", 24: "亲子剧", 25: "戏曲", 26: "舞蹈", 27: "脱口秀", 28: "相声", 29: "杂技马戏", 30: "展览", 31: "乐园市集",
    32: "剧本密室", 33: "演讲讲座", 34: "其他玩乐", 35: "赛事", 36: "电竞", 37: "健身运动", 38: "儿童剧", 39: "沉浸式", 40: "旅游"
}


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



class CySupplierInfo(models.Model):
    """供应商信息模型"""
    name = models.CharField(max_length=200, verbose_name='供应商名称')
    supplier_id = models.CharField(max_length=100, verbose_name='供应商ID')

    class Meta:
        verbose_name = '供应商信息'
        verbose_name_plural = '供应商信息'

    def __str__(self):
        return self.name


class CyGroupInfo(models.Model):
    """项目组合信息模型"""
    group_id = models.CharField(max_length=100, verbose_name='项目组合ID')
    group_name = models.CharField(max_length=200, verbose_name='项目组合名称')

    class Meta:
        verbose_name = '项目组合信息'
        verbose_name_plural = '项目组合信息'

    def __str__(self):
        return self.group_name


class CyCategory(models.Model):
    """项目组合信息模型"""
    code = models.PositiveSmallIntegerField(verbose_name='节目分类编码', unique=True)
    name = models.CharField(max_length=20, verbose_name='名称')

    class Meta:
        verbose_name_plural = verbose_name = '节目分类'

    @classmethod
    def init(cls):
        for code, name in EVENT_CATEGORIES.items():
            cate, _ = cls.objects.get_or_create(code=code, name=name)
            ShowType.objects.get_or_create(name=name, cy_cate=cate)

    @classmethod
    def get_cate(cls, code):
        return cls.objects.get(code=code)


class CyShowEvent(models.Model):
    """事件/项目模型"""
    # 基本信息
    show = models.OneToOneField(ShowProject, verbose_name='演出项目', on_delete=models.CASCADE, related_name='cy_show')
    event_id = models.CharField(max_length=100, unique=True, db_index=True, verbose_name='项目ID')
    std_id = models.CharField(max_length=100, verbose_name='中心项目ID')
    # 座位和票务信息
    SEAT_HAS = 1
    SEAT_NO = 0
    seat_type = models.PositiveSmallIntegerField(
        choices=[(SEAT_NO, '非选座'), (SEAT_HAS, '选座')],
        default=SEAT_NO,
        verbose_name='项目座位类型'
    )
    MD_DEFAULT = 0
    MD_PRICE = 1
    MD_SEAT = 2
    ticket_mode = models.PositiveSmallIntegerField(
        choices=[(MD_DEFAULT, '无'), (MD_PRICE, '票价库存'), (MD_SEAT, '座位库存')],
        default=MD_DEFAULT,
        verbose_name='库存类型'
    )
    # 媒体信息
    poster_url = models.URLField(verbose_name='项目海报地址', blank=True, null=True)
    content_url = models.URLField(verbose_name='项目简介链接', blank=True, null=True)
    category = models.IntegerField(
        choices=[
            (1, '演出'),
            (2, '赛事'),
            (3, '活动'),
            (4, '展览')
        ],
        default=1,
        verbose_name='节目大类'
    )
    # 状态信息
    state = models.IntegerField(
        choices=[
            (1, '待开售'),
            (2, '预售中'),
            (3, '售票中'),
            (4, '延期'),
            (5, '取消'),
            (6, '未开售'),
            (7, '已结束')
        ],
        default=1,
        verbose_name='节目状态'
    )
    supplier_info = models.ForeignKey(
        CySupplierInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='供应商信息'
    )
    group_info = models.ForeignKey(
        CyGroupInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='项目组合信息'
    )

    # 时间信息
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name_plural = verbose_name = '节目'
        ordering = ['-pk']

    def __str__(self):
        return self.show.title

    @property
    def is_selectable_seat(self):
        """是否为选座项目"""
        if self.ticket_mode is not None:
            return self.ticket_mode == 2
        return self.seat_type == 1

    @property
    def is_selling(self):
        """是否正在售票"""
        return self.state in [2, 3]  # 预售中或售票中

    @property
    def is_ended(self):
        """是否已结束"""
        return self.state == 7

    @property
    def is_cancelled(self):
        """是否已取消"""
        return self.state == 5
