# coding: utf-8
from __future__ import unicode_literals
from django.db import models
from datetime import timedelta
from django.conf import settings
import logging
from random import sample
from mall.models import User
from common.utils import get_config, save_url_img
from django.core.exceptions import ValidationError
from django.utils import timezone
from restframework_ext.exceptions import CustomAPIException
import json
from typing import List, Dict
from django.db.transaction import atomic
from caiyicloud.api import caiyi_cloud
from ticket.models import ShowProject, ShowType, Venues
from common.config import IMAGE_FIELD_PREFIX
import os

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


class CyCategory(models.Model):
    """项目组合信息模型"""
    code = models.PositiveSmallIntegerField(verbose_name='节目分类编码', unique=True)
    name = models.CharField(max_length=20, verbose_name='名称', null=True)

    class Meta:
        verbose_name_plural = verbose_name = '节目分类'

    @classmethod
    def init(cls):
        for code, name in EVENT_CATEGORIES.items():
            cate, _ = cls.objects.get_or_create(code=code, name=name)
            ShowType.objects.get_or_create(name=name, cy_cate=cate)

    @classmethod
    def get_show_type(cls, code: str, name: str):
        need = False
        inst, create = cls.objects.get_or_create(code=code)
        if create:
            inst.name = name
            inst.save(update_fields=['name'])
            need = True
        else:
            show_type = ShowType.objects.filter(cy_cate=inst).first()
            if not show_type:
                need = True
        if need:
            show_type, _ = ShowType.objects.get_or_create(name=name)
            show_type.cy_cate = inst
            show_type.save(update_fields=['cy_cate'])
            show_type.show_type_copy_to_pika()
        return inst, show_type


class CyVenue(models.Model):
    venue = models.OneToOneField(Venues, verbose_name='演出场馆', on_delete=models.CASCADE, related_name='cy_venue')
    province_name = models.CharField("省", max_length=32)
    city_name = models.CharField("市", max_length=32)
    cy_no = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='场馆ID')

    class Meta:
        verbose_name_plural = verbose_name = '场馆'
        ordering = ['-pk']

    def __str__(self):
        return self.venue.name

    @classmethod
    def create_record(cls, venue, province_name, city_name, cy_no):
        return cls.objects.create(venue=venue, province_name=province_name, city_name=city_name, cy_no=cy_no)


class CyShowEvent(models.Model):
    """事件/项目模型"""
    # 基本信息
    show = models.OneToOneField(ShowProject, verbose_name='演出项目', on_delete=models.CASCADE, related_name='cy_show')
    event_id = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='项目ID')
    std_id = models.CharField(max_length=64, verbose_name='中心项目ID')
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
    expire_order_minute = models.PositiveSmallIntegerField('订单支付等待时间', help_text='单位：分钟')
    snapshot = models.TextField('其他信息', null=True, blank=True, editable=False)
    # 时间信息
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name_plural = verbose_name = '节目'
        ordering = ['-pk']

    def __str__(self):
        return self.show.title

    @classmethod
    def get_show_status(cls, state: int):
        if state == 3:
            return ShowProject.STATUS_ON
        return ShowProject.STATUS_OFF

    @property
    def check_can_on(self):
        """是否可以上架"""
        return self.state not in [5, 7]

    @classmethod
    def init_cy_event(cls):
        cy = caiyi_cloud()
        # try:
        page = 1
        page_size = 50
        event_data = cy.get_events(page=page, page_size=page_size)
        total = event_data['total']
        event_list = event_data.get('list') or []
        while total > page * page_size and page < 50:
            page += 1
            event_data = cy.get_events(page=page, page_size=page_size)
            if event_data.get('list'):
                event_list += event_data['list']
        for event in event_list:
            event_detail = cy.event_detail(event['id'])
            show_type = CyCategory.get_show_type(event_detail['type'], event_detail['type_desc'])
            cy_venue = CyVenue.objects.filter(cy_no=event_detail['venue_id']).first()
            if not cy_venue:
                venue_detail = cy.venue_detail(event_detail['venue_id'])
                from express.models import Division
                city = Division.objects.filter(province=venue_detail['province_name'], city=venue_detail['city_name'],
                                               type=Division.TYPE_CITY).first()
                venue = Venues.objects.create(name=venue_detail['name'], city=city,
                                              lat=venue_detail['latitude'], lng=venue_detail['longitude'],
                                              address=venue_detail['address'], desc=venue_detail['description'],
                                              custom_mobile=venue_detail['venue_phone'])
                CyVenue.create_record(venue, venue_detail['province_name'], venue_detail['city_name'],
                                      event_detail['venue_id'])
                venue.venues_detail_copy_to_pika()
            else:
                venue = cy_venue.venue
            notice = ''
            if event_detail.get('watching_notices'):
                notice += '观演须知:\n'
                for nt in event_detail['watching_notices']:
                    notice += f"{nt['title']}:\n{nt['content']}\n"
            if event_detail.get('purchase_notices'):
                notice += '购买须知:\n'
                for nt in event_detail['purchase_notices']:
                    notice += f"{nt['title']}:\n{nt['content']}\n"
            logo_mobile_dir = f'{IMAGE_FIELD_PREFIX}/ticket/shows'
            # 保存网络图片
            logo_mobile_path = save_url_img(event_detail['poster_url'], logo_mobile_dir)
            show_data = dict(title=event_detail['name'], show_type=show_type, venues=venue, lat=venue.lat,
                             lng=venue.lng,
                             city_id=venue.city.id, sale_time=timezone.now(), content=event_detail['content'],
                             notice=notice, status=cls.get_show_status(event_detail['state']),
                             logo_mobile=logo_mobile_path)
            cy_show_qs = cls.objects.filter(event_id=event['id'])
            snapshot = dict(supplier_info=event_detail.get('supplier_info'), group_info=event_detail['group_info'])
            cls_data = dict(event_id=event['id'], std_id=event_detail['std_id'], seat_type=event_detail['seat_type'],
                            ticket_mode=event_detail.get('ticket_mode', cls.MD_DEFAULT),
                            poster_url=event_detail['poster_url'],
                            content_url=event_detail['content_url'], category=event_detail['category'],
                            expire_order_minute=event_detail['expire_order_minute'], snapshot=json.dumps(snapshot))
            if not cy_show_qs:
                show = ShowProject.objects.create(**show_data)
                cls_data['show'] = show
                cls.objects.create(**cls_data)
            else:
                show = cy_show_qs.first().show
                ShowProject.objects.filter(id=show.id).update(**show_data)
                cy_show_qs.update(**cls_data)
            show.shows_detail_copy_to_pika()
        # except Exception as e:
        #     log.error(e)
