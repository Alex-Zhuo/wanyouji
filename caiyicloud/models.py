# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models
from django.conf import settings
import logging
from mall.models import User
from common.utils import get_config, save_url_img
from django.core.exceptions import ValidationError
from django.utils import timezone
from restframework_ext.exceptions import CustomAPIException
import json
from typing import List, Dict
from django.db.transaction import atomic
from caiyicloud.api import caiyi_cloud
from ticket.models import ShowProject, ShowType, Venues, SessionInfo, TicketFile
from common.config import IMAGE_FIELD_PREFIX
from datetime import datetime, timedelta
from django.db import models
from django.core.validators import MinValueValidator
import re
from decimal import Decimal
from caches import get_redis, get_redis_name

log = logging.getLogger(__name__)
"""
节目分类字典
"""
EVENT_CATEGORIES = {
    17: "演唱会", 18: "音乐节", 19: "Livehouse", 20: "话剧", 21: "歌剧", 22: "音乐剧",
    23: "音乐会", 24: "亲子剧", 25: "戏曲", 26: "舞蹈", 27: "脱口秀", 28: "相声", 29: "杂技马戏", 30: "展览", 31: "乐园市集",
    32: "剧本密室", 33: "演讲讲座", 34: "其他玩乐", 35: "赛事", 36: "电竞", 37: "健身运动", 38: "儿童剧", 39: "沉浸式", 40: "旅游"
}


def init_all():
    CyCategory.init_record()
    CyIdTypes.init_record()
    CyCheckInMethods.init_record()
    CyDeliveryMethods.init_record()


class ChoicesCommon(models.Model):
    code = models.PositiveSmallIntegerField('编码', unique=True)
    name = models.CharField(max_length=64, verbose_name='名称', null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    INIT_DATA = []

    @classmethod
    def init_record(cls):
        for v in cls.INIT_DATA:
            cls.objects.get_or_create(code=v[0], name=v[1])


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


class CyCategory(ChoicesCommon):
    class Meta:
        verbose_name_plural = verbose_name = '节目分类'

    INIT_DATA = list(EVENT_CATEGORIES.items())

    @classmethod
    def get_show_type(cls, code: str, name: str):
        need = False
        show_type = None
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

    @classmethod
    def init_venue(cls, cy_venue_id: str):
        cy_venue = CyVenue.objects.filter(cy_no=cy_venue_id).first()
        if not cy_venue:
            cy = caiyi_cloud()
            venue_detail = cy.venue_detail(cy_venue_id)
            from express.models import Division
            city = Division.objects.filter(province=venue_detail['province_name'], city=venue_detail['city_name'],
                                           type=Division.TYPE_CITY).first()
            venue = Venues.objects.create(name=venue_detail['name'], city=city,
                                          lat=venue_detail['latitude'], lng=venue_detail['longitude'],
                                          address=venue_detail['address'], desc=venue_detail['description'],
                                          custom_mobile=venue_detail['venue_phone'])
            CyVenue.create_record(venue, venue_detail['province_name'], venue_detail['city_name'], cy_venue_id)
            venue.venues_detail_copy_to_pika()
        else:
            venue = cy_venue.venue
        return venue


class CyShowEvent(models.Model):
    # 基本信息
    show = models.OneToOneField(ShowProject, verbose_name='演出项目', on_delete=models.CASCADE, related_name='cy_show')
    category = models.PositiveSmallIntegerField(
        choices=[
            (1, '演出'),
            (2, '赛事'),
            (3, '活动'),
            (4, '展览')
        ],
        default=1,
        verbose_name='节目大类'
    )
    show_type = models.ForeignKey(CyCategory, verbose_name='节目分类', on_delete=models.SET_NULL, null=True)
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
    # 状态信息
    state = models.PositiveSmallIntegerField(
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
    def init_cy_show(cls, is_refresh=False):
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
        redis = get_redis()
        key = get_redis_name('cyiniteventkey')
        has_change_event_list = redis.lrange(key, 0, -1) or []
        for event in event_list:
            if is_refresh or event['id'] not in has_change_event_list:
                cls.update_or_create_record(event['id'])
                redis.lpush(key, event['id'])
            CySession.init_cy_session(event['id'], is_refresh)
        if is_refresh:
            redis.delete(key)

    @classmethod
    @atomic
    def update_or_create_record(cls, event_id: str):
        cy = caiyi_cloud()
        event_detail = cy.event_detail(event_id)
        cy_show_type, show_type = CyCategory.get_show_type(event_detail['type'], event_detail['type_desc'])
        venue = CyVenue.init_venue(event_detail['venue_id'])
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
        cy_show_qs = cls.objects.filter(event_id=event_id)
        snapshot = dict(supplier_info=event_detail.get('supplier_info'), group_info=event_detail['group_info'])
        cls_data = dict(event_id=event_id, std_id=event_detail['std_id'], seat_type=event_detail['seat_type'],
                        show_type=cy_show_type, ticket_mode=event_detail.get('ticket_mode') or cls.MD_DEFAULT,
                        poster_url=event_detail['poster_url'],
                        content_url=event_detail['content_url'], category=event_detail['category'],
                        expire_order_minute=event_detail['expire_order_minute'], snapshot=json.dumps(snapshot))
        if not cy_show_qs:
            show = ShowProject.objects.create(**show_data)
            cls_data['show'] = show
            cy_show = cls.objects.create(**cls_data)
        else:
            cy_show = cy_show_qs.first()
            show = cy_show.show
            ShowProject.objects.filter(id=show.id).update(**show_data)
            cy_show_qs.update(**cls_data)
        show.shows_detail_copy_to_pika()
        return cy_show
    # except Exception as e:
    #     log.error(e)


class CyIdTypes(ChoicesCommon):
    class Meta:
        verbose_name_plural = verbose_name = '证件类型'
        ordering = ['-pk']

    INIT_DATA = [
        (1, '身份证'),
        (2, '护照'),
        (4, '军人证'),
        (8, '台湾居民来往内地通行证'),
        (16, '港澳居民来往内地大陆通行证'),
        (32, '港澳居民居住证'),
        (64, '台湾居民居住证'),
        (128, '外国人永久居留身份证'),
    ]


class CyCheckInMethods(ChoicesCommon):
    class Meta:
        verbose_name_plural = verbose_name = '入场方式'
        ordering = ['-pk']

    # 入场方式选择
    INIT_DATA = [
        (1, '纸质票'),
        (2, '电子票'),
        (4, '身份证'),
    ]


class CyDeliveryMethods(ChoicesCommon):
    class Meta:
        verbose_name_plural = verbose_name = '配送方式'
        ordering = ['-pk']

    # 配送方式选择
    INIT_DATA = [
        (2, '电子票（直刷入场）'),
        (4, '快递票'),
        (8, '电子票（现场取票）'),
        (32, '电子票（身份证直刷入场）'),
        (64, '身份证换票'),
    ]


class CySession(models.Model):
    SESSION_STATE_CHOICES = [
        (1, '未开售'),
        (2, '待开售'),
        (3, '预售中'),
        (4, '售票中'),
        (5, '结束'),
        (6, '延期'),
        (7, '取消'),
    ]
    # 场次类型选择
    SESSION_TYPE_CHOICES = [
        (0, '普通场次'),
        (1, '联票场次'),
    ]
    # 入场码类型选择
    ADMISSION_CODE_TYPE_CHOICES = [
        (0, '联票码'),
        (1, '基础场次票码'),
    ]
    # 电子票类型选择
    E_TICKET_CHOICES = [
        (0, '不支持电子票'),
        (1, '静态码'),
        (2, '动态码'),
    ]
    # 结束售卖类型选择
    CLOSE_SALE_TYPE_CHOICES = [
        (1, '场次开始前'),
        (2, '场次结束前'),
        (3, '场次开始后'),
    ]
    # 基本信息
    c_session = models.OneToOneField(SessionInfo, verbose_name='演出场次', on_delete=models.CASCADE,
                                     related_name='cy_session')
    # 关联信息
    event = models.ForeignKey(CyShowEvent, on_delete=models.CASCADE, verbose_name='关联节目')
    cy_no = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='场次ID')
    std_id = models.CharField(max_length=64, verbose_name='中心场次ID')
    start_time = models.DateTimeField('开始时间', db_index=True)
    end_time = models.DateTimeField('结束时间', db_index=True)
    sale_time = models.DateTimeField('开售时间', null=True, blank=True)
    name = models.CharField(max_length=200, verbose_name='场次名称')
    state = models.PositiveSmallIntegerField(choices=SESSION_STATE_CHOICES, default=1, verbose_name='场次状态')
    # 场次类型
    session_type = models.PositiveSmallIntegerField(choices=SESSION_TYPE_CHOICES, default=0, verbose_name='场次类型')
    admission_code_type = models.PositiveSmallIntegerField(
        choices=ADMISSION_CODE_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name='入场码类型'
    )
    upload_photo = models.PositiveSmallIntegerField(
        choices=[(0, '无需上传照片'), (1, '需上传照片')],
        null=True,
        blank=True,
        verbose_name='是否需要上传照片'
    )
    # 选座相关
    support_no_seat = models.PositiveSmallIntegerField(
        choices=[(0, '不支持非选座购票'), (1, '支持非选座购票')],
        null=True,
        blank=True,
        verbose_name='是否支持非选座购票'
    )
    # 证件相关
    require_id_on_ticket = models.PositiveSmallIntegerField(
        choices=[(0, '否'), (1, '是')],
        default=1,
        verbose_name='是否需要一票一证购买'
    )
    id_types = models.ManyToManyField(CyIdTypes, verbose_name='证件类型列表', blank=True)
    # 票务相关
    e_ticket = models.PositiveSmallIntegerField(choices=E_TICKET_CHOICES, default=1, verbose_name='电子票类型')
    paper_ticket = models.PositiveSmallIntegerField(
        choices=[(0, '否'), (1, '是')],
        default=1,
        verbose_name='是否支持纸质票出票'
    )
    check_in_methods = models.ManyToManyField(CyCheckInMethods, verbose_name='入场方式列表', blank=True)
    delivery_methods = models.ManyToManyField(CyDeliveryMethods, verbose_name='配送方式列表', blank=True)
    # 结束售卖时间相关
    enable_close_sale_time = models.PositiveSmallIntegerField(
        choices=[(0, '禁用'), (1, '启用')],
        default=0,
        verbose_name='是否开启结束售卖时间设置'
    )
    close_sale_time_rule_type = models.PositiveSmallIntegerField(
        choices=[(1, '相对时间'), (2, '绝对时间')],
        null=True,
        blank=True,
        verbose_name='结束售卖时间规则类型'
    )
    close_sale_time = models.DateTimeField(null=True, blank=True, verbose_name='结束售卖时间')
    close_sale_time_interval = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='场次关闭时间间隔(小时)'
    )
    close_sale_type = models.PositiveSmallIntegerField(
        choices=CLOSE_SALE_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name='结束售卖类型'
    )
    # 限购信息
    limit_on_session = models.PositiveSmallIntegerField(default=6, verbose_name='单场次限购张数')
    limit_on_event = models.PositiveSmallIntegerField(default=20, verbose_name='单节目限购张数')

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name_plural = verbose_name = '场次'
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.name} - {self.get_state_display()}"

    @property
    def is_on_sale(self):
        """是否正在售票"""
        return self.state == 4

    @property
    def is_ended(self):
        """是否已结束"""
        return self.state == 5

    @property
    def is_cancelled(self):
        """是否已取消"""
        return self.state == 7

    @classmethod
    def get_session_status(cls, state: int):
        if state == 4:
            return SessionInfo.STATUS_ON
        return SessionInfo.STATUS_OFF

    def get_id_types_display(self):
        """获取证件类型显示文本"""
        if not self.id_types.all():
            return "无"
        qs = list(self.id_types.all().values_list('name', flat=True))
        return ", ".join(qs)

    def get_check_in_methods_display(self):
        """获取入场方式显示文本"""
        if not self.check_in_methods.all():
            return "无"
        qs = list(self.check_in_methods.all().values_list('name', flat=True))
        return ", ".join(qs)

    def get_delivery_methods_display(self):
        """获取配送方式显示文本"""
        if not self.delivery_methods.all():
            return "无"
        qs = list(self.delivery_methods.all().values_list('name', flat=True))
        return ", ".join(qs)

    @classmethod
    def init_cy_session(cls, event_id: str, is_refresh=False):
        cy = caiyi_cloud()
        cy_show = CyShowEvent.objects.filter(event_id=event_id).first()
        if not cy_show:
            cy_show = CyShowEvent.update_or_create_record(event_id)
        sessions_data = cy.sessions_list(event_id=event_id)
        page = 1
        page_size = 50
        total = sessions_data['total']
        session_list = sessions_data.get('list') or []
        while total > page * page_size and page < 50:
            page += 1
            sessions_data = cy.sessions_list(event_id=event_id, page=page, page_size=page_size)
            if sessions_data.get('list'):
                session_list += sessions_data['list']
        redis = get_redis()
        key = get_redis_name('cyinitsessionkey')
        has_change_session_list = redis.lrange(key, 0, -1) or []
        tk_key = get_redis_name('cyinitticketkey')
        has_change_ticket_list = redis.lrange(tk_key, 0, -1) or []
        for api_data in session_list:
            if is_refresh or api_data['id'] not in has_change_session_list:
                cls.update_or_create_record(cy_show, api_data)
                redis.lpush(key, api_data['id'])
            # 更新票档
            if is_refresh or api_data['id'] not in has_change_ticket_list:
                CyTicketType.update_or_create_record(api_data['id'])
                redis.lpush(tk_key, api_data['id'])
        if is_refresh:
            redis.delete(key)
            redis.delete(tk_key)

    @classmethod
    @atomic
    def update_or_create_record(cls, cy_show: CyShowEvent, api_data: dict):
        # 处理时间字段
        start_time = None
        end_time = None
        sale_time = None
        close_sale_time = None
        if api_data.get('start_time'):
            start_time = datetime.strptime(api_data['start_time'], '%Y-%m-%d %H:%M:%S')
        if api_data.get('end_time'):
            end_time = datetime.strptime(api_data['end_time'], '%Y-%m-%d %H:%M:%S')
        if api_data.get('sale_time'):
            sale_time = datetime.strptime(api_data['sale_time'], '%Y-%m-%d %H:%M:%S')
        if api_data.get('close_sale_time'):
            close_sale_time = datetime.strptime(api_data['close_sale_time'], '%Y-%m-%d %H:%M:%S')
        # 创建场次
        # 创建限购信息
        limit_on_session = 0
        limit_on_event = 0
        if api_data.get('purchase_limit'):
            limit_on_session = api_data['purchase_limit'].get('limit_on_session', 0)
            limit_on_event = api_data['purchase_limit'].get('limit_on_event', 0)
        require_id_on_ticket = True if api_data.get('require_id_on_ticket') else False
        cls_data = dict(
            event=cy_show,
            cy_no=api_data['id'],
            std_id=api_data.get('std_id'),
            name=api_data['name'],
            state=api_data['state'],
            start_time=start_time,
            end_time=end_time,
            sale_time=sale_time,
            session_type=api_data.get('session_type', 0),
            admission_code_type=api_data.get('admission_code_type'),
            upload_photo=api_data.get('upload_photo'),
            support_no_seat=api_data.get('support_no_seat'),
            require_id_on_ticket=api_data.get('require_id_on_ticket'),
            # id_types=api_data.get('id_types', []),
            e_ticket=api_data.get('e_ticket', 1),
            paper_ticket=api_data.get('paper_ticket', 1),
            # check_in_methods=api_data.get('check_in_methods', []),
            # delivery_methods=api_data.get('delivery_methods', []),
            enable_close_sale_time=api_data.get('enable_close_sale_time', 1),
            close_sale_time_rule_type=api_data.get('close_sale_time_rule_type'),
            close_sale_time=close_sale_time,
            close_sale_time_interval=api_data.get('close_sale_time_interval'),
            close_sale_type=api_data.get('close_sale_type'),
            limit_on_session=limit_on_session,
            limit_on_event=limit_on_event
        )
        show = cy_show.show
        has_seat = SessionInfo.SEAT_HAS if cy_show.seat_type == 1 else SessionInfo.SEAT_NO
        session_data = dict(show=show, venue_id=show.venues.id, title=api_data['name'], start_at=start_time,
                            end_at=end_time, dy_sale_time=sale_time, order_limit_num=limit_on_session,
                            one_id_one_ticket=require_id_on_ticket, name_buy_num=1 if require_id_on_ticket else 0,
                            is_name_buy=True, has_seat=has_seat, status=cls.get_session_status(api_data['state']))
        cy_session_qs = cls.objects.filter(cy_no=api_data['id'])
        if not cy_session_qs:
            session = SessionInfo.objects.create(**session_data)
            cls_data['c_session'] = session
            cy_session = cls.objects.create(**cls_data)
        else:
            cy_session = cy_session_qs.first()
            session = cy_session.c_session
            SessionInfo.objects.filter(id=session.id).update(**session_data)
            cy_session_qs.update(**cls_data)
        # 修改多选
        id_types_list = api_data.get('id_types', [])
        if id_types_list:
            ct_list = []
            for code in id_types_list:
                ct = CyIdTypes.objects.filter(code=code).first()
                if ct:
                    ct_list.append(ct)
            if ct_list:
                cy_session.id_types.set(ct_list)
        check_in_list = api_data.get('check_in_methods', [])
        if check_in_list:
            ci_list = []
            for code in check_in_list:
                ci = CyCheckInMethods.objects.filter(code=code).first()
                if ci:
                    ci_list.append(ci)
            if ci_list:
                cy_session.check_in_methods.set(ci_list)
        delivery_list = api_data.get('delivery_methods', [])
        if delivery_list:
            dl_list = []
            for code in delivery_list:
                dl = CyDeliveryMethods.objects.filter(code=code).first()
                if dl:
                    dl_list.append(dl)
            if dl_list:
                cy_session.delivery_methods.set(dl_list)
        show.change_session_end_at(session.end_at)
        # 修改缓存
        show.shows_detail_copy_to_pika()
        session.redis_show_date_copy()
        return cy_session

    def get_seat_url(self, ticket_type_id: str, navigate_url: str):
        cy = caiyi_cloud()
        try:
            data = cy.seat_url(self.event.event_id, self.cy_no, ticket_type_id, navigate_url)
            return data
        except Exception as e:
            raise CustomAPIException(e)


class CyTicketPack(models.Model):
    """套票子项模型"""
    cy_no = models.CharField(max_length=64, unique=True, db_index=True, help_text="套票子项id")
    ticket_type_id = models.CharField(max_length=50, help_text="票档-票价id")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="基础票价格", default=0)
    qty = models.IntegerField(validators=[MinValueValidator(1)], help_text="数量", default=1)

    class Meta:
        verbose_name_plural = verbose_name = '套票子项'

    def __str__(self):
        return f"{self.ticket_type_id} x{self.qty}"

    @classmethod
    def update_or_create_record(cls, cy_no: str, ticket_type_id: str, price: float, qty: int):
        obj, _ = cls.objects.get_or_create(cy_no=cy_no, ticket_type_id=ticket_type_id)
        obj.price = price
        obj.qty = qty
        obj.save(update_fields=['price', 'qty'])


class CyTicketType(models.Model):
    # 类别选择
    CATEGORY_CHOICES = [
        (1, '基础票'),
        (2, '固定套票'),
        (3, '自由套票'),
    ]
    # 启用状态选择
    ENABLED_CHOICES = [
        (0, '未启用'),
        (1, '启用'),
    ]
    # 停售状态选择
    SOLD_OUT_CHOICES = [
        (1, '可售'),
        (2, '停售'),
    ]
    ticket_file = models.OneToOneField(TicketFile, verbose_name='票档', on_delete=models.CASCADE,
                                       related_name='cy_tf')
    cy_session = models.ForeignKey(CySession, on_delete=models.CASCADE, verbose_name='关联节目')
    # 基础字段
    cy_no = models.CharField(max_length=64, unique=True, db_index=True, help_text="票价id")
    std_id = models.CharField(max_length=64, help_text="中心票价id")
    name = models.CharField(max_length=50, help_text="票价名称")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="票价，单位：元")
    comment = models.CharField(max_length=50, blank=True, null=True, help_text="票价说明")
    color = models.CharField(max_length=20, help_text="颜色", null=True, blank=True)
    # 状态字段
    enabled = models.IntegerField(
        choices=ENABLED_CHOICES,
        default=1,
        help_text="是否启用，1：启用；0：未启用"
    )
    sold_out_state = models.IntegerField(
        choices=SOLD_OUT_CHOICES,
        blank=True,
        null=True,
        help_text="是否停售, 1:可售，2:停售"
    )
    # 分类和排序
    category = models.IntegerField(
        choices=CATEGORY_CHOICES,
        default=1,
        help_text="类别，1：基础票，2：固定套票，3:自由套票"
    )
    seq = models.IntegerField(default=1, help_text="票价顺序")
    # 套票关联
    ticket_pack_list = models.ManyToManyField(
        CyTicketPack,
        blank=True,
        help_text="套票组成信息，基础票为空"
    )
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")

    class Meta:
        verbose_name_plural = verbose_name = '票档'
        ordering = ['seq', 'price']

    def __str__(self):
        return f"{self.name} - ¥{self.price}"

    @property
    def is_package_ticket(self):
        """是否为套票"""
        return self.category in [2, 3]

    @property
    def is_available(self):
        """是否可售"""
        return self.enabled == 1 and self.sold_out_state != 2

    def get_total_package_price(self):
        """获取套票总价"""
        if not self.is_package_ticket:
            return self.price

        total = 0
        for pack in self.ticket_pack_list.all():
            total += pack.price * pack.qty
        return total

    def get_package_items_count(self):
        """获取套票包含的票种数量"""
        if not self.is_package_ticket:
            return 0

        total_qty = 0
        for pack in self.ticket_pack_list.all():
            total_qty += pack.qty
        return total_qty

    def validate_color(self):
        """验证颜色格式"""
        if self.color:
            color_pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
            if not re.match(color_pattern, self.color):
                raise ValueError("颜色格式不正确，应为十六进制格式，如 #4a7fb3")

    # def clean(self):
    #     """模型验证"""
    #     super().clean()
    #     self.validate_color()
    #     # 套票验证
    #     if self.is_package_ticket and not self.ticket_pack_list.exists():
    #         raise ValueError("套票必须包含套票组成信息")
    #     if self.category ==1 and self.ticket_pack_list.exists():
    #         raise ValueError("基础票不能包含套票组成信息")
    #
    # def save(self, *args, **kwargs):
    #     self.clean()
    #     super().save(*args, **kwargs)

    @classmethod
    @atomic
    def update_or_create_record(cls, cy_session_id: str):
        cy = caiyi_cloud()
        cy_session = CySession.objects.filter(cy_no=cy_session_id).first()
        if cy_session:
            ticket_types_list = cy.ticket_types([cy_session_id])
            ticket_stock_list = cy.ticket_stock([cy_session_id])
            ticket_stock_dict = dict()
            for ticket_stock in ticket_stock_list:
                ticket_stock_dict[ticket_stock['ticket_type_id']] = ticket_stock
            for ticket_type in ticket_types_list:
                stock = 0
                if ticket_stock_dict.get(ticket_type['id']):
                    stock = int(ticket_stock_dict.get(ticket_type['id'])['inventory'])
                price = Decimal(ticket_type['price'])
                cls_data = dict(
                    cy_session=cy_session,
                    cy_no=ticket_type['id'],
                    name=ticket_type['name'],
                    std_id=ticket_type['std_id'],
                    price=price,
                    comment=ticket_type['comment'],
                    color=ticket_type['color'],
                    enabled=ticket_type['enabled'],
                    sold_out_state=ticket_type['sold_out_state'],
                    category=ticket_type['category'],
                    seq=ticket_type['seq'],
                )
                desc = f"{ticket_type['name']}({ticket_type['comment']})" if ticket_type['comment'] else ticket_type[
                    'name']
                status = True if ticket_type['enabled'] == 1 and ticket_type['sold_out_state'] == 1 else False
                tf_data = dict(session=cy_session.c_session, origin_price=price, price=price, stock=stock,
                               color_code=ticket_type['color'],
                               desc=desc, status=status)
                cy_ticket_qs = cls.objects.filter(cy_no=ticket_type['id'])
                if not cy_ticket_qs:
                    tf = TicketFile.objects.create(**tf_data)
                    cls_data['ticket_file'] = tf
                    cy_ticket = cls.objects.create(**cls_data)
                else:
                    cy_ticket = cy_ticket_qs.first()
                    tf = cy_ticket.ticket_file
                    TicketFile.objects.filter(id=tf.id).update(**tf_data)
                    cy_ticket_qs.update(**cls_data)
                # 添加套票组成
                ticket_pack_list = ticket_type.get('ticket_pack_list') or []
                if ticket_pack_list:
                    pack_list = []
                    for pack_data in ticket_pack_list:
                        pack = CyTicketPack.update_or_create_record(pack_data['id'], pack_data['ticket_type_id'],
                                                                    Decimal(pack_data['price']), int(pack_data['qty']))
                        pack_list.append(pack)
                    if pack_list:
                        cy_ticket.ticket_pack_list.set(pack_list)
                # 改缓存
                tf.redis_ticket_level_cache()

    @classmethod
    def get_seat_info(cls, biz_id):
        cy = caiyi_cloud()
        try:
            data = cy.seat_info(biz_id)
            return data
        except Exception as e:
            raise CustomAPIException(e)
