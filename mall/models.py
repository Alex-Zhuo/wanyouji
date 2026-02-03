# coding: utf-8
from __future__ import unicode_literals
import datetime
import json
import logging
import os
import time
from decimal import Decimal
from random import randint
from urllib.parse import quote
from functools import reduce
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.db.models.functions import Concat
from django.db.models import Manager
from django.db.transaction import atomic
from django.utils import timezone
from django.core.exceptions import ValidationError

from common.config import IMAGE_FIELD_PREFIX
from common.utils import get_common_uuid, secure_update
from wechatpy.exceptions import WeChatPayException
from express.models import Template, Division, ExpressCompany
from mall.mall_conf import normal_user_group_id, general_admin_group_id, notify_url, umf_notify_url, \
    city_manager_group_id, forum_staff_group_id
from mall.utils import randomstrwithdatetime, gen_user_share_code, randomstrwithdatetime_card, \
    random_theater_card_no, random_theater_order_no, gen_user_u_id
from mp.models import WeiXinPayConfig, DouYinPayConfig
from restframework_ext.exceptions import CustomAPIException
from .pay_service import get_mp_pay_client
from caches import get_by_key, get_pika_redis, get_redis_name
from mp.wechat_client import get_mp_client
from django.db.models.functions import Cast
from django.db.models import CharField
from django.db.models import Value
from restframework_ext.models import ReceiptAbstract
from django.db.models import F
from common.utils import close_old_connections, random_str
from renovation.models import SubPages
from datetime import timedelta
from django.core.validators import validate_image_file_extension
from caches import run_with_lock,get_redis_name
log = logging.getLogger(__name__)


def validate_positive_int_gen(min=1, max=None):
    """
    检查整数范围
    :param min:
    :param max:
    :return:
    """

    def validate_positive_int(value):
        """

        :param min:
        :param max:
        :return:
        """
        if not (min <= value and (max is None or (max and value <= max))):
            raise ValidationError('必须大于%s%s' % (min, (('大于%s' % max) if max else '')))
        return value

    return validate_positive_int


class User(AbstractUser):
    FOLLOW_CHOICES = [(0, '未关注'), (1, '已关注'), (2, '取消关注')]
    parent = models.ForeignKey('self', null=True, verbose_name=u'上级用户', blank=True, related_name='children',
                               on_delete=models.SET_NULL)
    path = models.CharField(u'路径', null=True, max_length=1024, blank=True, )
    province = models.CharField(u'省', null=True, max_length=20, help_text=u'省', blank=True)
    city = models.CharField(u'市', null=True, max_length=20, help_text=u'市', blank=True)
    county = models.CharField(u'区/县', null=True, max_length=20, help_text=u'区/县', blank=True)
    address = models.CharField(u'收货地址', null=True, max_length=255, blank=True)
    first_name = models.CharField(u'姓名', max_length=30, blank=True)
    icon = models.ImageField('头像', null=True, blank=True, upload_to=f'{IMAGE_FIELD_PREFIX}/mall/user/icons',
                             validators=[validate_image_file_extension])
    openid = models.CharField('openid', max_length=50, help_text='微信openid', null=True, blank=True, unique=True)
    uniacid = models.CharField(u'公众号id', max_length=20, help_text='公众号id', null=True, blank=True)
    token = models.CharField('token', max_length=60, null=True, blank=True, unique=True)
    avatar = models.CharField(u'微信头像', max_length=255, help_text='头像', null=True, blank=True)
    parent_openid = models.CharField('推荐人openid', max_length=50, help_text='推荐人openid', null=True, blank=True)
    is_wechat_register = models.BooleanField('是否微信注册', default=False)
    is_binding_mobile = models.BooleanField('是否已绑定', default=True)
    share_code = models.CharField('share_code', max_length=32, null=True, unique=True, db_index=True)
    mobile = models.CharField('手机', max_length=20, null=True, blank=True, db_index=True, unique=True)
    idcard = models.CharField('身份证', max_length=20, null=True, blank=True, editable=False)
    wechat = models.CharField('微信号', max_length=20, null=True, blank=True, editable=False)
    follow = models.SmallIntegerField('是否关注', default=0, choices=FOLLOW_CHOICES)
    FLAG_DEFAULT = 0
    FLAG_BUY = 1
    FLAG_CHOICES = [(FLAG_DEFAULT, '无'), (FLAG_BUY, '0.01购票')]
    flag = models.SmallIntegerField('用户权限', default=FLAG_DEFAULT, choices=FLAG_CHOICES)
    has_lock_seat = models.BooleanField('是否有手动出票权限', default=False)
    followtime = models.DateTimeField('关注时间', null=True)
    unfollowtime = models.DateTimeField('取消关注时间', null=True)
    last_name = models.CharField('昵称', max_length=30, blank=True, null=True)
    last_update_time = models.DateTimeField('上次更新信息时间', null=True, blank=True)
    wx_access_token = models.CharField('微信access_token', max_length=500, null=True, blank=True)
    level = models.IntegerField('层级', default=0)
    has_paid_order = models.BooleanField('是否有已付款礼包订单', default=False)
    qrcode_version = models.IntegerField('qrcode_version', default=0)
    session_key = models.CharField('小程序session_key', max_length=80, null=True, blank=True)
    own_session_key = models.CharField('登录session_key', max_length=80, null=True, blank=True, editable=False)
    unionid = models.CharField('unionid', max_length=50, help_text='开放平台unionid', null=True, unique=True)
    lp_openid = models.CharField('小程序openid', max_length=50, null=True, unique=True, db_index=True)
    session_key_tiktok = models.CharField('抖音小程序session_key', max_length=80, null=True, blank=True)
    unionid_tiktok = models.CharField('抖音unionid', max_length=50, null=True, unique=True)
    openid_tiktok = models.CharField('抖音小程序openid', max_length=50, null=True, unique=True, db_index=True)
    coordinates = models.CharField('用户默认位置坐标', max_length=120, null=True, help_text='纬度,经度')
    app_openid = models.CharField('app_openid', max_length=50, help_text='App_openid', null=True, blank=True)
    iv = models.IntegerField('iv', default=1, help_text='info的版本号')
    parent_at = models.DateTimeField('绑定上级时间', null=True, blank=True)
    new_parent = models.ForeignKey('self', verbose_name=u'最新推荐人', null=True, blank=True, related_name='+',
                                   on_delete=models.SET_NULL)
    new_parent_at = models.DateTimeField('被推荐时间', null=True, blank=True)
    agree_member = models.BooleanField('已签署用户协议', default=False)
    agree_privacy = models.BooleanField('已签署隐私政策', default=False)
    agree_agent = models.BooleanField('已开启Ai智能体服务', default=False)
    has_delete = models.BooleanField('是否有删除权限', default=False)
    has_add = models.BooleanField('是否有增加权限', default=False)
    has_change = models.BooleanField('是否有修改权限', default=False)
    is_tg = models.BooleanField('是否技术人员账号', default=False)
    forbid_order = models.BooleanField('是否禁止下单', default=False, help_text='勾选后不允许下单')
    day_visit_at = models.DateTimeField('当日登录时间', null=True, blank=True)

    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'
        # swappable = 'AUTH_USER_MODEL'

    def __str__(self):
        return self.get_full_name()

    ROLE_NONE = 0
    ROLE_SUPER = 1
    ROLE_STORE = 2
    ROLE_TICKET = 3
    ROLE_MANAGE = 4

    def get_new_parent(self):
        from mall.user_cache import get_new_parent_cache
        agent = get_new_parent_cache(self.id)
        return agent
        # card_agent = None
        # if self.new_parent and self.new_parent.account.is_agent():
        #     card_agent = self.new_parent
        # else:
        #     if self.parent and self.parent.account.is_agent():
        #         card_agent = self.parent
        # return card_agent

    # def set_new_parent(self, parent):
    #     if parent.id != self.id and parent.account.is_agent():
    #         self.new_parent = parent
    #         self.new_parent_at = timezone.now()
    #         self.save(update_fields=['new_parent', 'new_parent_at'])

    def send_notice(self):
        from mp.models import SystemMP
        from common.config import get_config
        from mall.mall_conf import host, share_index_s, share_index_center
        from push import MpTemplateClient
        mp = SystemMP.get()
        config = get_config()
        domain = config.get('templete_url') or host
        create_time = self.date_joined.strftime('%Y年%m月%d日%H:%M分')
        name = self.get_full_name()
        if self.parent and self.parent.openid:
            url = '{}{}'.format(domain, share_index_s)
            MpTemplateClient.parent_notice(self.parent.openid, mp.parent_head, mp.parent_end,
                                           name, create_time, url)
        if self.openid:
            url = '{}{}'.format(domain, share_index_center)
            MpTemplateClient.user_notice(self.openid, mp.user_head, mp.user_end, name, create_time, url)

    def get_cards(self):
        return dict(theater_card_amount=0, card_deadline=None)
        tc_card = TheaterCardUserRecord.objects.filter(user_id=self.id).first()
        theater_card_amount = tc_card.amount if tc_card else 0
        inst = CardRecord.objects.filter(user_id=self.id).first()
        card_deadline = inst.deadline_at if inst and inst.deadline_at and inst.deadline_at >= timezone.now().date() else None
        data = dict(theater_card_amount=theater_card_amount, card_deadline=card_deadline)
        return data

    @property
    def role(self):
        """
        返回后台账号的角色
        :return:
        """
        if self.is_superuser:
            return self.ROLE_SUPER
        elif self.groups.filter(name='店铺组').exists():
            return self.ROLE_STORE
        elif self.groups.filter(name='票务管理组').exists():
            return self.ROLE_TICKET
        elif self.groups.filter(name='巡演运营组').exists():
            return self.ROLE_MANAGE
        else:
            return self.ROLE_NONE

    def set_delete(self):
        fields = ['token', 'is_active']
        self.token = None
        self.is_active = False
        if self.unionid_tiktok:
            self.unionid_tiktok = '{}_{}'.format(self.unionid_tiktok, self.id)
            fields.append('unionid_tiktok')
        if self.openid_tiktok:
            self.openid_tiktok = '{}_{}'.format(self.openid_tiktok, self.id)
            fields.append('openid_tiktok')
        if self.session_key_tiktok:
            self.session_key_tiktok = '{}_{}'.format(self.session_key_tiktok, self.id)
            fields.append('session_key_tiktok')
        if self.lp_openid:
            self.lp_openid = '{}_{}'.format(self.lp_openid, self.id)
            fields.append('lp_openid')
        if self.unionid:
            self.unionid = '{}_{}'.format(self.unionid, self.id)
            fields.append('unionid')
        if self.openid:
            self.openid = '{}_{}'.format(self.openid, self.id)
            fields.append('openid')
        if self.mobile:
            self.mobile = '{}_{}'.format(self.mobile, self.id)
            fields.append('mobile')
        self.save(update_fields=fields)
        from mall.user_cache import share_code_user_cache_delete
        share_code_user_cache_delete(share_code=self.share_code)

    def set_info(self, mobile, first_name=None):
        update_fields = []
        if self.mobile != mobile:
            update_fields.append('mobile')
            self.mobile = mobile
        if first_name and self.first_name != first_name:
            self.first_name = first_name
            update_fields.append('first_name')
        if update_fields:
            self.save(update_fields=update_fields)

    def set_parent_null(self):
        self.parent = None
        self.save(update_fields=['parent'])

    @classmethod
    def get_default_agent(cls):
        from common.config import get_config
        company_id = get_config()['company_user']
        return cls.objects.filter(id=int(company_id)).first()

    def info(self, request):
        from mall.serializers import UserInfoSerializer
        return UserInfoSerializer(instance=self, context=dict(request=request)).data

    @property
    def account(self):
        if not hasattr(self, 'user_account'):
            from shopping_points.models import UserAccount
            return UserAccount.create(self)
        return self.user_account

    def generate_token(self):
        ts = str(int(time.time()))
        rand_str = random_str(10)
        from common.utils import md5_content
        head = md5_content(str(self.id) + rand_str) + str(self.id)
        return '_'.join([head, ts])

    def renew_token(self):
        # 新逻辑不需要存数据库
        return self.generate_token()

        # self.token = self.generate_token()
        # self.save(update_fields=['token'])
        # return self.token

    def biz_get_info_dict(self):
        # 每次登陆刷新，会触发signal，login_refresh_cache要放在最后
        share_code = self.get_share_code()
        token = self.biz_get_token()
        self.refresh_user_cache(token)
        return dict(actoken=token, mobile=self.mobile,
                    share_code=share_code, id=self.id)

    def biz_get_token(self):
        return self.renew_token()
        # if self.token:
        #     try:
        #         s, timestamp = self.token.split('_')
        #         from mall.user_cache import TOKEN_EXPIRE_HOURS
        #         if TOKEN_EXPIRE_HOURS * 3600 < time.time() - int(timestamp):
        #             self.renew_token()
        #     except Exception as e:
        #         self.renew_token()
        # else:
        #     self.renew_token()
        # return self.token

    # compliant with old implemention
    get_token = biz_get_token

    @classmethod
    def verify_by_token(cls, token):
        """
        通过token验证用户, 需要考虑token是否过期。
        :param token:
        :return:
            验证通过返回User对象
        """
        # 新逻辑token不存user了
        return None
        # try:
        #     user = cls.objects.get(token=token)
        #     rtoken = user.biz_get_token()
        #     return user if token == rtoken else None
        # except cls.DoesNotExist:
        #     return None

    def biz_get_info(self):
        """
        获取token和积分余额
        :return:
        """
        return self.point_balance, self.biz_get_token()

    @staticmethod
    def autocomplete_search_fields():
        return 'last_name', 'id', 'mobile'

    def get_display_name(self):
        return self.first_name or self.last_name or self.username

    get_display_name.short_description = '名称'

    def get_full_name(self):
        return self.last_name or self.mobile or self.username

    get_full_name.short_description = '用户'

    # def get_token(self, nonce=None):
    #     """
    #     nonce should be unique as possible.
    #     :param nonce:
    #     :return:
    #     """
    #     if not self.token:
    #         m = md5()
    #         m.update(str(time.time()) + (nonce or self.username))
    #         self.token = m.hexdigest()
    #         self.save(update_fields=['token'])
    #     return self.token

    @property
    def can_bind_child(self):
        """
        是否可以绑定下级
        :return:
        """
        return True

    @property
    def can_be_bind(self):
        """
        是否还可以被上级绑定
        :return:
        """
        st = False
        if self.parent_at:
            # 3个月解绑
            year = timezone.now().year
            month = timezone.now().month
            if year - self.parent_at.year > 0:
                month = month + 12 * (year - self.parent_at.year)
            if (month - self.parent_at.month) >= 3:
                st = True
        else:
            st = True
        return st
        # return self.parent_id is None

    def bind_another_will_cause_circle(self, another):
        """
        返回：会形成环
        :param another:
        :return:
        """

        def check_circle():
            """
            返回: 不会形成环,即可以绑定

            :return:
            """
            res = self.id not in another.__class__.objects.filter(
                path__startswith=another.path + '/').values_list('id', flat=True)
            if not res:
                log.fatal('%s want to bind %s, which has a circle' % (self.pk, another.pk))
            return res

        return not check_circle()

    def can_bind_another(self, another):
        """
        我是否能绑定another
        :param another: 被绑定的人
        :return:
        """

        def check_circle():
            # 改成不判断环
            return True
            """
            返回: 不会形成环,即可以绑定
            :return:
            """
            res = self.id not in another.__class__.objects.filter(
                path__startswith=another.path + '/').values_list('id', flat=True)
            if not res:
                log.fatal('%s want to bind %s, which has a circle' % (self.pk, another.pk))
            return res

        return (
                another and another.id != self.id and another.can_be_bind
                and self.can_bind_child
                and check_circle())

    def bind_parent(self, share_code=None, parent=None):
        """
        根据share_code或parent绑定分享人，统一入口
        :param parent: 上级用户
        :param share_code: 分享码（与parent二取1）
        :return:
        """
        if not (share_code or parent):
            raise CustomAPIException('参数错误:010')
        # log.warning(share_code)
        if share_code:
            from mall.user_cache import share_code_to_user
            # 3个月没有重新登陆的用户则不绑定
            parent = share_code_to_user(share_code)
        else:
            parent = parent
        if parent:
            # log.warning(parent.id)
            # 每次都更新 新上级，用于订单绑定 代理或者验票员
            # self.set_new_parent(parent)
            if self.id != parent.id:
                from mall.user_cache import bind_new_parent
                bind_new_parent(self.id, parent)
            if parent.can_bind_another(self):
                if parent.pk != self.parent_id:
                    self.parent_id = parent.id
                    self.parent_at = timezone.now()
                    self.save(update_fields=['parent', 'parent_at'])
                else:
                    self.parent_at = timezone.now()
                    self.save(update_fields=['parent_at'])

    @classmethod
    def mobile_get_user(cls, mobile):
        user = cls.objects.filter(mobile=mobile, is_active=True).first()
        return user

    def combine_user(self, mobile, source_type: int, request, first_name=None):
        fields = []
        user = None
        if source_type == 1:
            # 小程序端, 绑定手机合并用户
            fields = ['unionid', 'openid', 'lp_openid', 'icon', 'avatar', 'token', 'follow', 'followtime',
                      'unfollowtime', 'last_name']
        elif source_type == 2:
            # 抖音合并
            fields = ['unionid_tiktok', 'openid_tiktok', 'session_key_tiktok']
        elif source_type == 3:
            # 快手合并写在快手的独立模块 check_user_ks
            pass
        if fields:
            user = self.do_combine_user(mobile, fields, request, first_name)
        from coupon.tasks import coupon_bind_user_task
        coupon_bind_user_task.delay(mobile, user.id)
        return user

    def do_combine_user(self, mobile, fields: list, request, first_name=None):
        # 执行合并用户
        uu = self
        user = User.mobile_get_user(mobile)
        from restframework_ext.permissions import get_token
        token = get_token(request)
        if user and self.id != user.id:
            log.debug(user.id)
            log.debug(self.id)
            if not user.parent and self.parent:
                # 旧用户上级为空而且当前用户有上级
                fields = fields + ['parent', 'parent_at']
            for fd in fields:
                setattr(user, fd, getattr(self, fd))
            if first_name:
                user.first_name = first_name
                fields.append('first_name')
            # 当前用户设为无效，删除缓存逻辑，前端自动重新登陆
            self.set_delete()
            user.save(update_fields=fields)
            # 新的最新推荐人，覆盖到旧的上面
            from mall.user_cache import change_new_parent
            change_new_parent(self.id, user.id)
            uu = user
            user.refresh_user_cache(token)
        else:
            uu.set_info(mobile, first_name)
        return uu

    @classmethod
    def gen_username(cls):
        return randomstrwithdatetime(tail_length=4)

    def get_balance(self):
        return self.account.balance

    def update_address_info(self, wechat_user):
        update_fields = ['province', 'city', 'county', 'address', 'addressee']
        self.province = wechat_user.province
        self.city = wechat_user.city
        self.county = wechat_user.county
        self.address = wechat_user.address
        self.addressee = wechat_user.addressee
        return update_fields

    def _clear_wechat_info(self):
        self.openid = None
        self.parent_openid = None
        self.save(update_fields=['openid', 'parent_openid'])

    def do_merge_wechat_user(self, wechat_user):
        update_fields = ['openid', 'uniacid']
        self.openid = wechat_user.openid
        self.uniacid = wechat_user.uniacid
        update_fields.extend(self._feed_parent_openid(wechat_user.parent_openid))
        wechat_user._clear_wechat_info()
        return update_fields

    @atomic
    def merge_wechat_user(self, wechat_user):
        update_fields = self.update_address_info(wechat_user)
        if self.openid:
            self.save(update_fields=update_fields)
            return
        update_fields.extend(self.do_merge_wechat_user(wechat_user))
        self.save(update_fields=update_fields)
        wechat_user.disable()

    def _feed_parent_openid(self, parent_openid):
        user = self
        update_fields = []
        if parent_openid and '0' != parent_openid and not user.parent:
            # todo: if parent currently not has a account, just set the parent_openid,
            # should set the parent when the account created
            user.parent_openid = parent_openid
            update_fields.append('parent_openid')
            parent = User.objects.filter(openid=parent_openid).first()

            if parent:
                user.parent = parent
                update_fields.append('parent')
        return update_fields

    def disable(self):
        self.is_active = False
        self.is_staff = False
        self.token = None
        self.save(update_fields=['is_active', 'is_staff', 'token'])

    @atomic
    def logged_user_merge_new_comming_wechat_user(self, user):
        logged_user = self
        if not logged_user.openid:
            self.save(update_fields=self.do_merge_wechat_user(user))
        if logged_user != user:
            user.disable()

    @staticmethod
    def is_login(request):
        return request.user and request.user.is_active and request.user.is_staff

    @classmethod
    def create_from_mp(cls, openid, nickname=None, avatar=None, share_code=None, follow=0,
                       followtime=None, unionid=None):
        """
        当确认用户不存在情况下，调用该方法创建用户.场景：公众号，关注、网页
        :param openid:
        :param nickname:
        :param avatar:
        :param share_code:
        :param follow:
        :param followtime:
        :param unionid:
        :return:
        """
        temp_name = cls.gen_username()
        log.debug('get sharecode {}'.format(share_code))
        parent = User.objects.filter(share_code=share_code).first() if share_code else None
        if parent and not parent.can_bind_child:
            log.debug('the parent can not lock child')
            # 不能锁定下级
            parent = None
        return User.objects.create(is_staff=False,
                                   is_active=True, username=temp_name, openid=openid,
                                   last_name=nickname or temp_name, avatar=avatar, is_wechat_register=True,
                                   parent=parent, follow=follow, followtime=followtime,
                                   level=(parent.level + 1) if parent else 1, unionid=unionid)

    def new_user_getpoint(self, childname):
        from shopping_points.models import UserPointChangeRecord
        amount = randint(1, 10) * Decimal('0.1')
        # log.debug('get share_ponint {}'.format(amount))
        UserPointChangeRecord.objects.create(account=self.account, amount=amount,
                                             source_type=UserPointChangeRecord.SOURCE_TYPE_SHARE,
                                             desc=u'(%s)新用户登录获得消费金' % childname)
        self.account.update_point_balance(amount, True)

    @classmethod
    def create_from_lp(cls, openid, unionid=None, nickname=None, avatar=None, session_key=None,
                       share_code=None, lpid=None):
        """
        当用户不存在情况，创建用户。场景：小程序
        :param openid:
        :param unionid:
        :param nickname:
        :param avatar:
        :param session_key:
        :param share_code:
        :return:
        """

        # from shopping_points.models import FreeGoodChaneRecord
        def default():
            defaults = dict()
            # if origin == 0:
            defaults['lp_openid'] = openid
            defaults['unionid'] = unionid
            defaults['session_key'] = session_key
            defaults['last_name'] = nickname
            defaults['avatar'] = avatar
            log.info("unionid: %s, defaults: %s" % (unionid, defaults))
            defaults['username'] = cls.gen_username()
            inst = User.objects.create(**defaults)
            # User.add_freegoodchanerecord(user=inst, record_type=FreeGoodChaneRecord.RECORD_TYPE_MY_NEW)
            if session_key and inst.session_key != session_key:
                defaults.pop('username', None)
                log.debug("defaults is: %s" % defaults)
                uf = secure_update(inst, **defaults)
                log.debug("update_fields: %s" % uf)
            if share_code:
                inst.bind_parent(share_code)
                # from mall.celery_tasks import bind_parent_task
                # bind_parent_task.delay(inst.id, share_code)
            if inst.parent:
                # 首次注册绑定上级送一次转盘
                from blind_box.models import UserLotteryTimesDetail
                UserLotteryTimesDetail.add_record(inst.parent, times=1, source_type=UserLotteryTimesDetail.SR_NEW,
                                                  add_total=True)
            return inst

        def ext():
            # todo: not support new login way
            defaults = dict()
            # if origin == 0:
            # defaults['lp_openid'] = openid
            defaults['session_key'] = session_key
            defaults['last_name'] = nickname
            defaults['avatar'] = avatar
            log.info("unionid: %s, defaults: %s" % (unionid, defaults))
            defaults['username'] = cls.gen_username()
            inst = User.objects.create(unionid=unionid, **defaults)
            # User.add_freegoodchanerecord(user=inst, record_type=FreeGoodChaneRecord.RECORD_TYPE_MY_NEW)
            # LpId.objects.create(lpid=lpid, lp_openid=openid, session_key=session_key, user=inst)
            if share_code:
                inst.bind_parent(share_code)
                # from mall.celery_tasks import bind_parent_task
                # bind_parent_task.delay(inst.id, share_code)
            if inst.parent:
                from blind_box.models import UserLotteryTimesDetail
                UserLotteryTimesDetail.add_record(inst.parent, times=1, source_type=UserLotteryTimesDetail.SR_NEW,
                                                  add_total=True)
            return inst

        if lpid:
            return ext()
        else:
            return default()

    @classmethod
    def update_from_lp(cls, user, nickname=None, avatar=None, session_key=None,
                       share_code=None, lpid=None):
        """
        小程序的session_key会定时过期，过期后更新信息.
        :param openid:
        :param unionid:
        :param nickname:
        :param avatar:
        :param session_key:
        :param share_code:
        :return:
        """

        def default():
            defaults = dict()
            defaults['session_key'] = session_key
            defaults['last_name'] = nickname
            defaults['avatar'] = avatar
            log.debug("defaults is: %s" % defaults)
            uf = secure_update(user, **defaults)
            log.debug("update_fields: %s" % uf)
            if share_code:
                user.bind_parent(share_code)
                # from mall.celery_tasks import bind_parent_task
                # bind_parent_task.delay(user.id, share_code)
            return user

        def ext():
            defaults = dict()
            # defaults['session_key'] = session_key
            defaults['last_name'] = nickname
            defaults['avatar'] = avatar
            log.debug("defaults is: %s" % defaults)
            uf = secure_update(user, **defaults)
            log.debug("update_fields: %s" % uf)
            lpid = user.lpid_set.first()
            secure_update(lpid, session_key=session_key)
            if share_code:
                # 放celery里
                user.bind_parent(share_code)
                # mall.celery_tasks import bind_parent_task
                # bind_parent_task.delay(user.id, share_code)
            return user

        if lpid:
            return ext()
        else:
            return default()

    @classmethod
    def get_by_wechat(cls, openid=None, lp_openid=None, unionid=None, lpid=None):
        """
        查询用户, 根据三者之一. openid和lp_openid至少有一个，要么是一个openid或lp_openid，要么是unionid+openid(或lp_openid)
        若unionid找到用户，则可能补全openid或者lp_openid.找不到用户则返回空
        :type lpid: int, 小程序编号，支持多小程序.
        :param openid: 公众号openid
        :param lp_openid: 小程序openid
        :param unionid: 可空
        :return:
        """

        def default_lp():
            if not (openid or lp_openid):
                raise CustomAPIException('参数错误，缺少微信标识')
            try:
                search_dict = dict()
                q = None
                if unionid:
                    q = models.Q(unionid=unionid)
                    search_dict['unionid'] = unionid
                if openid:
                    if q:
                        q = q | models.Q(openid=openid)
                    else:
                        q = models.Q(openid=openid)
                    search_dict['openid'] = openid
                else:
                    if q:
                        q = q | models.Q(lp_openid=lp_openid)
                    else:
                        q = models.Q(lp_openid=lp_openid)
                    search_dict['lp_openid'] = lp_openid

                user = cls.objects.filter(q).get()
                for k, v in search_dict.items():
                    cv = getattr(user, k, None)
                    if cv is None:
                        setattr(user, k, v)
                        user.save(update_fields=[k])
                        break
                    elif cv != v:
                        raise CustomAPIException('标识冲突')
                return user
            except cls.DoesNotExist:
                return
            except cls.MultipleObjectsReturned:
                raise CustomAPIException('标识冲突2')

        return default_lp()

    @classmethod
    def get_by_openid(cls, opend_id, unionid=None, lpid=None):
        """
        该方法为遗留方法，公众号相关的获取用户使用的是此方法。新的调用应该使用get_by_wechat
        通过openid或unionid查询用户,目前都是用在创建用户之前查询用户, 优先从unionid获取.调用点包括网页登录处、关注事件、取关事件等等
        支持多小程序
        :param opend_id:
        :param unionid:
        :return:
        """
        return cls.get_by_wechat(openid=opend_id, unionid=unionid, lpid=lpid)

    @classmethod
    def get_or_create_by_lp(cls, unionid, openid=None, nickname=None, avatar=None, session_key=None,
                            share_code=None, lpid=None):
        """
        小程序入口使用该方法查询或创建用户、包含更新session_key.
        支持多小程序
        :param unionid:
        :param openid:
        :param nickname:
        :param avatar:
        :param session_key:
        :param share_code:
        :return:
        """
        user = cls.get_by_wechat(lp_openid=openid, unionid=unionid, lpid=lpid)
        if not user:
            return cls.create_from_lp(openid, unionid, nickname, avatar, session_key, share_code, lpid)
        else:
            return cls.update_from_lp(user, nickname, avatar, session_key, share_code, lpid)

    @classmethod
    def push_auth_zhihui(cls, unionid, openid=None, nickname=None, avatar=None, origin=0, session_key=None,
                         share_code=None, lpid=None):
        """
        小程序场景，创建或更新用户.兼容旧方法，新的应该调用get_or_create_by_lp
        :param unionid:
        :param openid:
        :param nickname:
        :param avatar:
        :param origin: 废弃的参数
        :param session_key:
        :param share_code:
        :return:
        """
        return cls.get_or_create_by_lp(unionid, openid, nickname, avatar, session_key, share_code, lpid)

    @classmethod
    def dep_push_auth_zhihui(cls, unionid, openid=None, nickname=None, avatar=None, origin=0, session_key=None,
                             share_code=None):
        """
        接收小程序、web网站扫码登陆来源的推送.根据unionid查询或创建用户.
        OpenWeixinView里调用，包括小程序授权、web网站扫码登录（开放平台）,
        其中对于web网站登录这块是为杭州养老项目定制的，如果需要使用，还需要梳理一下逻辑。
        :param share_code: 分享码
        :param session_key: 小程序专有的
        :param avatar: 头像
        :param unionid:
        :param openid: 小程序或者网站openid
        :param nickname: 昵称
        :param origin: 0 小程序, 1 app
        :return:
          user
        """
        defaults = dict()
        if origin == 0:
            defaults['lp_openid'] = openid
            defaults['session_key'] = session_key
        defaults['last_name'] = nickname
        defaults['avatar'] = avatar
        log.info("unionid: %s, defaults: %s" % (unionid, defaults))
        defaults['username'] = cls.gen_username()
        inst, created = User.objects.get_or_create(unionid=unionid, defaults=defaults)
        if not created and session_key and inst.session_key != session_key:
            defaults.pop('username', None)
            log.debug("defaults is: %s" % defaults)
            uf = secure_update(inst, **defaults)
            log.debug("update_fields: %s" % uf)
        if share_code:
            inst.bind_parent(share_code)
            # from mall.celery_tasks import bind_parent_task
            # bind_parent_task.delay(inst.id, share_code)
        return inst

    @classmethod
    def auth_from_wechat(cls, openid, uniacid=None, nickname=None, avatar=None, share_code=None, follow=0,
                         followtime=None, unionid=None, app_openid=None, mobile=None):
        """
        新建用户。关注公众号、访问公众号网页时自动注册方法，目前调用点为：关注时间、mpwebview（网页授权登录）
        兼容旧方法，新的应该直接调用create_from_mp
        :param openid:
        :param uniacid: 废弃的参数
        :param nickname:
        :param avatar:
        :param share_code:
        :param follow:
        :param followtime:
        :param unionid:
        :return:
        """
        return cls.create_from_mp(openid, nickname, avatar, share_code, follow, followtime, unionid)

    @classmethod
    def auth_from_wechat_app(cls, openid, uniacid=None, nickname=None, avatar=None, share_code=None, follow=0,
                             followtime=None, unionid=None, app_openid=None, mobile=None):
        """
        :param openid:
        :param uniacid:
        :param nickname:
        :param avatar:
        :param share_code:  the share core of who share the link
        :param follow::
        :param followtime:
        :return:
        """
        try:
            if unionid:
                user = User.objects.get(unionid=unionid)
            else:
                user = User.objects.get(openid=openid)
            user.unionid = unionid
            user.openid = openid if openid else user.openid
            user.app_openid = app_openid if app_openid else user.app_openid
            user.save(update_fields=['openid', 'app_openid', 'unionid'])
        except User.DoesNotExist:
            temp_name = cls.gen_username()
            log.debug('get sharecode {}'.format(share_code))
            parent = User.objects.filter(share_code=share_code).first() if share_code else None
            if parent and not parent.can_bind_child:
                log.debug('the parent can not lock child')
                # 不能锁定下级
                parent = None
            user = User.objects.create(is_active=True, username=mobile or temp_name, openid=openid, uniacid=uniacid,
                                       last_name=nickname or mobile or temp_name,
                                       avatar=avatar, is_wechat_register=True,
                                       parent=parent, follow=follow, followtime=followtime,
                                       level=(parent.level + 1) if parent else 1,
                                       unionid=unionid, app_openid=app_openid, mobile=mobile,
                                       is_staff=True)
        return user

    @classmethod
    def dep_auth_from_wechat(cls, openid, uniacid=None, nickname=None, avatar=None, share_code=None, follow=0,
                             followtime=None, unionid=None):
        """
        关注公众号、访问公众号网页时自动注册方法，目前调用点为：关注时间、mpwebview（网页授权登录）
        :param openid: 公众号openid
        :param uniacid: 公众号id, 没什么用
        :param nickname: 微信昵称
        :param avatar: 微信头像
        :param share_code:  the share core of who share the link. 邀请码
        :param follow: 是否关注
        :param followtime: 关注时间
        :return:
        """
        try:
            if not unionid:
                user = User.objects.get(openid=openid)
            else:
                user = User.objects.get(unionid=unionid)
        except User.DoesNotExist:
            temp_name = cls.gen_username()
            log.debug('get sharecode {}'.format(share_code))
            parent = User.objects.filter(share_code=share_code).first() if share_code else None
            if parent:
                if not parent.has_paid_order and not parent.user_account.level:
                    log.debug('the parent has no paid order, can not lock child')
                    # 上级没买过,不能锁定下级
                    parent = None
            user = User.objects.create(is_staff=True,
                                       is_active=True, username=temp_name, openid=openid, uniacid=uniacid,
                                       last_name=nickname or temp_name, avatar=avatar, is_wechat_register=True,
                                       parent=parent, follow=follow, followtime=followtime,
                                       level=(parent.level + 1) if parent else 1, unionid=unionid)
        return user

    @classmethod
    def get_or_create_by_openid(cls, openid=None, nickname=None, avatar=None, auth_token=None, share_code=None,
                                return_created=False):
        """
        这个可能是第三方平台方式时候使用的，目前不使用。
        :param openid:
        :param nickname:
        :param avatar:
        :param auth_token:
        :param share_code:
        :param return_created:
        :return:
        """
        if not openid and auth_token:
            openid = get_by_key(os.environ.get('INSTANCE_TOKEN') + auth_token)
        created = False
        try:
            user = User.objects.get(openid=openid)
        except User.DoesNotExist:
            parent = User.objects.filter(share_code=share_code).first() if share_code else None
            user = User.objects.create(is_active=True, username=cls.gen_username(), openid=openid,
                                       last_name=nickname or '', avatar=avatar, parent=parent,
                                       level=(parent.level + 1) if parent else 1)
            user.update_wechat_info()
            user.groups.add(Group.objects.get(id=normal_user_group_id))
            created = True
        return user if not return_created else (user, created)

    def update_parent_by_share_code(self, share_code, query_params=None):
        parent = User.objects.filter(share_code=share_code).first() if share_code else None
        if not self.has_paid_order:
            if parent and (parent.has_paid_order or parent.user_account.level) and parent != self.parent \
                    and parent != self and self != parent.parent:
                if parent.id not in self.__class__.objects.filter(
                        path__startswith=self.path + '/').values_list('id', flat=True):
                    self.parent = parent
                    self.level = parent.level + 1
                    self.path = '/'.join([parent.path, str(self.id)])
                    self.save(update_fields=['parent', 'level', 'path'])
                    # if not parent.account.level:
                    #     from shopping_points.models import FreeGoodChaneRecord
                    #     User.add_freegoodchanerecord(user=parent, record_type=FreeGoodChaneRecord.RECORD_TYPE_MY_CHILD)
                    self.refresh_tree()
                    # if topic:
                    #     UserTopicPullNewRecord.objects.get_or_create(user=self.parent, topic=topic, user_new=self)

    @staticmethod
    def logout_user(request, response):
        logout(request)
        if 'user' in request.COOKIES and request.COOKIES['user']:
            response.delete_cookie('user')

    def login_user(self, request, response):
        login(request, self)
        log.debug('user_login ....')
        token = self.get_token()
        data = json.dumps(dict(token=token, nickname=self.get_full_name(), id=self.id,
                               share_code=self.get_share_code()))
        response.set_cookie('user', quote(data))
        # 每次登陆刷新
        self.refresh_user_cache(token)

    def refresh_user_cache(self, token):
        from mall.user_cache import login_refresh_cache
        login_refresh_cache(token, self)

    def cache_info_token(self, token):
        key = get_redis_name('token_info_{}'.format(token))
        from mall.user_cache import TOKEN_EXPIRE_HOURS
        expire_in = TOKEN_EXPIRE_HOURS * 3600 - 10
        from mall.serializers import UserInfoCacheSerializer
        data = UserInfoCacheSerializer(self).data
        with get_pika_redis() as pika:
            pika.set(key, json.dumps(data))
            pika.expire(key, expire_in)

    def upgrade_member_level(self, incr=1):
        assert incr >= 1
        self.member_level += incr
        self.save(update_fields=['member_level'])
        return self.member_level

    def set_member_level(self, level):
        assert level >= 0
        self.member_level = level
        self.save(update_fields=['member_level'])
        return self.member_level

    def get_target_level_parent(self, level):
        maxtime = 30
        parent = self.parent
        while maxtime > 0 and parent:
            maxtime -= 1
            if parent.account.level.grade > level.grade:
                return parent
            else:
                parent = parent.parent
        return User.get_default_agent()

    def get_parent(self, level):
        assert level > 0
        while level > 0 and self:
            self = self.parent
            level -= 1
        return self

    def get_top_parent(self):
        user_find = self
        while user_find.parent:
            user_find = user_find.parent
        return user_find

    def update_iv(self):
        """
        更新info版本
        :return:
        """
        self.__class__.objects.filter(pk=self.pk).update(iv=models.F('iv') + 1)

    def refresh_my_tree(self):
        """
        更新自己和自己的孩子
        :return:
        """
        # 更新自己
        self.update_path()
        # 更新自己的孩子
        self.refresh_tree()

    def update_path(self, refresh=True):
        """
        与get_or_update_path不同，如果是要更新自己，则调用这个。
        这个基于父节点是正确的才能保证正确，否则也是错的
        :return:
        """
        if refresh:
            self.refresh_from_db(fields=['parent', 'path', 'level'])
        if self.parent:
            parent_path = self.parent.get_or_update_path()
            if parent_path:
                self.path = '/'.join([parent_path, str(self.id)])
                self.level = self.parent.level + 1
                self.save(update_fields=['path', 'level'])
            else:
                log.warning("the parent: %s can't init path" % self.parent.id)
            return self.path
        else:
            self.path = '/%s' % self.id
            self.level = 1
            self.save(update_fields=['path', 'level'])

    def get_or_update_path(self):
        """
        该方法会检查没有path的user对象, 为其设置path，仅适合创建对象的场景.
        该方法不会改变path属性, 比如改变了上级的情况。update_path才是基于上级更新自己的情况
        :return:
        """
        if self.path:
            return self.path
        elif self.parent_id:
            parent_path = self.parent.get_or_update_path()
            if parent_path:
                self.path = '/'.join([parent_path, str(self.id)])
                self.level = self.parent.level + 1
                self.save(update_fields=['path', 'level'])
            else:
                log.warning("the parent: %s can't init path" % self.parent.id)
            return self.path
        else:
            # the top node
            self.path = '/%s' % self.id
            self.save(update_fields=['path'])
            return self.path

    def refresh_tree(self, chain=None):
        """
        更新自己的孩子。更新子节点，前提是自己是正确的。使用场景：当自己的上级更换时
        如果关系成环状，存在死循环的可能 #todo: 如何避免？
        :return:
        """
        if chain:
            if self.id in chain:
                log.fatal('occur circle tree, %s+ %s' % (chain, self.id))
                raise CustomAPIException('用户关系冲突: cc003')
            else:
                chain.add(self.id)
        else:
            chain = {self.id}
        self.children.update(level=self.level + 1, path=Concat(Value(self.path + '/'), Cast('id', CharField())))
        for child in self.children.all():
            if child.id in chain:
                log.fatal('occur circle tree, %s + %s' % (chain, child.id))
                raise CustomAPIException('用户关系冲突: cc004')
            child.refresh_tree(chain)

    @classmethod
    def refresh_path_level(cls):
        """
        更新整个系统的用户树，从根开始
        :return:
        """
        cls.objects.filter(parent__isnull=True).update(level=1, path=Concat(Value('/'), Cast('id', CharField())))
        roots = cls.objects.filter(parent__isnull=True)
        for root in roots:
            root.refresh_tree()

    def approve(self, force=False):
        inst = self

        if force:
            inst.is_staff = True
            inst.is_active = True
            group = Group.objects.first()
            if not group:
                raise ValueError(u'还没有初始化权限"组"')
            inst.groups.add(group)
            inst.save(update_fields=['is_active', 'is_staff'])
            return
        dirty = False
        if not inst.is_active:
            inst.is_active = True
            dirty = True
        if not inst.is_staff:
            inst.is_staff = True
            dirty = True
        if not len(inst.groups.all()):
            group = Group.objects.first()
            if not group:
                raise ValueError(u'还没有初始化权限"组"')
            inst.groups.add(group)
        if dirty:
            inst.save(update_fields=['is_active', 'is_staff'])

    def get_share_code(self):
        if not self.share_code:
            # self.share_code = gen_user_share_code(self.id))
            self.share_code = get_common_uuid(self.id, 'sh')
            self.save(update_fields=['share_code'])
        return self.share_code

    def check_and_update_day_visit_at(self):
        st = False
        key = get_redis_name('day_visit{}'.format(self.id))
        with run_with_lock(key, 60) as got:
            if got:
                now = timezone.now()
                st = not self.day_visit_at or self.day_visit_at.date() < now.date()
                if st:
                    self.day_visit_at = now
                    self.save(update_fields=['day_visit_at'])
        return st

    # @classmethod
    # def uid_cache_key(cls):
    #     return get_redis_name('uidcache')
    #
    # def get_uid(self):
    #     uid = self.get_share_code()[:8]
    #     key = self.uid_cache_key()
    #     with get_pika_redis() as redis:
    #         user_id = redis.hget(key, uid)
    #         if not user_id:
    #             redis.hset(key, uid, self.id)
    #         elif int(user_id) != self.id:
    #             uid = gen_user_u_id(self.id, salt='fjuiriejhfgj565865@&*')
    #             redis.hset(key, uid, self.id)
    #     return uid
    #
    # @classmethod
    # def u_id_to_id(cls, uid: str):
    #     key = cls.uid_cache_key()
    #     with get_pika_redis() as redis:
    #         user_id = redis.hget(key, uid)
    #     return user_id

    @property
    def can_check_platform(self):
        if self.usertag_set.filter(tag__name='platform'):
            return True
        return False

    def update_wechat_info(self, interval_limit=True):
        """
        手动更新用户信息，使用公众号主动获取用户信息接口.关注时候、或者用户手动更新时调用
        :param interval_limit:是否限制更新频率
        :return:
        """
        if interval_limit:
            if self.last_update_time and (datetime.datetime.now() - self.last_update_time).days <= 1:
                return
        client = get_mp_client()
        info = client.get_user_info(open_id=self.openid)
        if info:
            if info.get('subscribe') == 0:
                if self.follow == 1:
                    self.follow = 0
                    self.unfollowtime = timezone.now()
                    self.save(update_fields=['follow', 'unfollowtime'])
            else:
                log.debug('get wechat user info {} user: {}'.format(info, self))
                self.last_name = info.get('nickname')
                self.avatar = info.get('headimgurl')
                self.last_update_time = datetime.datetime.now()
                self.follow = info.get('subscribe')
                self.followtime = datetime.datetime.fromtimestamp(info.get('subscribe_time')) \
                    if info.get('subscribe_time') else self.followtime
                self.qrcode_version = self.qrcode_version + 1
                self.save(update_fields=['last_name', 'avatar', 'last_update_time', 'follow', 'followtime',
                                         'qrcode_version'])

    def is_general_admin(self):
        return self.groups.filter(id=general_admin_group_id)

    def team_members(self, level=1, account_level=None, trial_member=False):
        # if level < 1:
        #     raise ValueError('level must be positive')
        if level == 0:
            qs = self.__class__.objects.filter(path__startswith=self.path + '/', level__gt=self.level).order_by(
                '-date_joined')
        else:
            qs = self.__class__.objects.filter(path__startswith=self.path + '/', level=self.level + level).order_by(
                '-date_joined')
        if account_level:
            if account_level == -1:
                # 查询没有级别的
                return qs.filter(user_account__level__isnull=True)
            else:
                return qs.filter(user_account__level=account_level)
        # if trial_member:
        #     return qs.filter(user_account__trial_member=True)
        return qs

    def team_members_with_invites(self, level=1, account_level=None, kw=None):
        """
        巴曼尔，合并平推团队.UserAccount.invites下的团队, 含invites
        :param level:
        :param account_level:
        :param kw:
        :return:
        """
        user = self
        invite_ids = list(user.account.invites.filter(level__isnull=False).values_list('user', flat=True))
        invites = User.objects.filter(pk__in=invite_ids)
        qs = user.team_members(level, account_level)
        ivs = [i.team_members(level, account_level) for i in invites]
        from shopping_points.models import UserAccount
        qs2 = User.objects.filter(id__in=invite_ids)
        if account_level:
            if account_level > 0:
                qs2 = qs2.filter(user_account__level=account_level)
            elif account_level == -1:
                qs2 = qs2.filter(user_account__level=None)
        if kw:
            qs = qs.filter(last_name__icontains=kw)
            ivs = [i.filter(last_name__icontains=kw) for i in ivs]
            qs2 = qs2.filter(last_name__icontains=kw)
        ivs.append(qs)
        ivs.append(qs2)
        qs = reduce(lambda a, b: a | b, ivs)
        qs = qs.distinct()
        return qs

    def team_total_count(self):
        """
        有付费的总团队数
        :return:
        """
        return self.__class__.objects.filter(path__startswith=self.path + '/').count()

    def clean(self):
        if self.parent == self:
            raise ValidationError(dict(parent=ValidationError('上级不能为自己')))
        if self.parent in self.children.all():
            raise ValidationError(dict(parent=ValidationError('上级不能为自己下级')))
        if self.parent:
            if self.path and self.parent.path.startswith(self.path):
                raise ValidationError(dict(parent=ValidationError('上级不能为自己团队成员')))

    @classmethod
    def update_wechat_info_job(cls):
        close_old_connections()
        for u in cls.objects.filter(openid__isnull=False):
            try:
                u.update_wechat_info()
            except Exception as e:
                continue

    @property
    def is_city_manager(self):
        if self.groups.filter(id=city_manager_group_id).exists():
            return True
        return False

    @property
    def is_forum_staff(self):
        return self.groups.filter(id=forum_staff_group_id).exists()

    # @pysnooper.snoop(log.debug)
    def check_can_be_parent(self, parent, raise_exception=False):
        """
        检查parent是否可以是我的父节点
        :param parent: None, long/int, User三种类型
        :param raise_exception:
        :return:
        """

        def valid(pid):
            if self.parent_id == pid:
                log.error('can not set self to parent')
                raise CustomAPIException('不能设置自己为上级')
            elif str(pid) in self.path.split('/')[1:]:
                log.error('can not set %s to %s \' parent' % (parent, self.path))
                raise CustomAPIException('关系冲突')
            return True

        def check():
            if parent is None:
                # 如果self.parent_id也是None，即不用修改，是None才需要修改返回True
                return self.parent_id is not None
            elif isinstance(parent, int):
                return valid(parent)
            elif isinstance(parent, User):
                return valid(parent.id)
            else:
                log.error('error type: %s, %s' % (parent, type(parent)))
                raise CustomAPIException('内部错误:u0091')

        try:
            return check()
        except CustomAPIException as e:
            if raise_exception:
                raise e
            else:
                return False

    def set_parent(self, parent):
        return
        """
        设置上级
        :param parent:
        :return:
        """
        log.debug('set %s\' parent from %s to %s' % (self.id, self.parent_id, parent))
        if not self.check_can_be_parent(parent, False):
            return False

        def update_with_refresh(pid):
            self.parent_id = pid
            update_fields = ['parent_id']
            self.save(update_fields=update_fields)
            self.update_path(True)
            # 更新子节点
            self.refresh_tree()
            return True

        if parent is None:
            pid = None
        elif isinstance(parent, int):
            pid = parent
        elif isinstance(parent, self.__class__):
            pid = parent.id
        else:
            log.error('wrong type of parent: %s' % type(parent))
            raise CustomAPIException('内部错误:u009')
        return update_with_refresh(pid)

    def secure_iterate_parents_new(self, callback, raise_exception=True, max_times=30, attachment=None):
        """
        从自己开始向跟节点查找父节点，检测了关系环的情形，保证不会出现死循环.
        计算奖励或其他需要遍历上级的场景，都应该使用这个方法.
        :param callback: 回调对象，
            def callback(parent, level, attachment=None):
                # level is the level's parent
                do something with parent
                return True, attachment # go continue to find, and attachment will pass to next find
                return False, result # stop finding
        :param raise_exception: True to raise exception when find circle or not for False
        :param max_times: max try times
        :return:
        返回callback方法返回的结果，或者返回None如果没找到上级
        """
        parents = [self.id]
        current = self
        level = 1
        clone = max_times
        while max_times > 0:
            if current.parent_id:
                if current.parent_id in parents:
                    log.fatal('#0001: the parent circle occur: %s, %s. tried %s times' % (
                        parents, current.parent_id, clone - max_times + 1))
                    if raise_exception:
                        raise CustomAPIException('关系冲突')
                    else:
                        return
                parents.append(current.parent_id)
                continue_to_find, result = callback(current.parent, level, attachment)
                if continue_to_find:
                    level += 1
                    current = current.parent  # and continue
                    attachment = result  # attachment
                else:
                    return result
            else:
                return
            max_times -= 1

    def secure_iterate_parents(self, callback, raise_exception=True, max_times=30):
        """
        从自己开始向跟节点查找父节点，检测了关系环的情形，保证不会出现死循环.
        计算奖励或其他需要遍历上级的场景，都应该使用这个方法.
        :param callback: 回调对象，
            def callback(parent, level, attachment=None):
                # level is the level's parent
                do something with parent
                return True, attachment # go continue to find, and attachment will pass to next find
                return False, result # stop finding
        :param raise_exception: True to raise exception when find circle or not for False
        :param max_times: max try times
        :return:
        返回callback方法返回的结果，或者返回None如果没找到上级
        """
        parents = [self.id]
        current = self
        level = 1
        clone = max_times
        attachment = None
        while max_times > 0:
            if current.parent_id:
                if current.parent_id in parents:
                    log.fatal('#0001: the parent circle occur: %s, %s. tried %s times' % (
                        parents, current.parent_id, clone - max_times + 1))
                    if raise_exception:
                        raise CustomAPIException('关系冲突')
                    else:
                        return
                parents.append(current.parent_id)
                continue_to_find, result = callback(current.parent, level, attachment)
                if continue_to_find:
                    level += 1
                    current = current.parent  # and continue
                    attachment = result  # attachment
                else:
                    return result
            else:
                return
            max_times -= 1

    def secure_iterate_parents_self(self, callback, raise_exception=True, max_times=30, attachment=dict()):
        '从自己开始循环'
        parents = []
        current = self
        level = 1
        clone = max_times
        attachment = attachment
        while max_times > 0:
            if current:
                if current in parents:
                    log.fatal('#0001: the parent circle occur: %s, %s. tried %s times' % (
                        parents, current, clone - max_times + 1))
                    if raise_exception:
                        raise CustomAPIException('关系冲突')
                    else:
                        return
                parents.append(current)
                continue_to_find, result = callback(current, level, attachment)
                if continue_to_find:
                    level += 1
                    current = current.parent  # and continue
                    attachment = result  # attachment
                else:
                    return result
            else:
                return
            max_times -= 1


class DateDetailAbstract(models.Model):
    create_at = models.DateTimeField(u'创建时间', auto_now_add=True)
    update_at = models.DateTimeField(u'更新时间', auto_now=True)

    class Meta:
        abstract = True


class Receipt(ReceiptAbstract):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'用户', related_name='receipts', null=True,
                             on_delete=models.SET_NULL)
    attachment = models.TextField('附加数据', null=True, blank=True, help_text='请勿修改此字段')
    BIZ_GOODS = 0
    BIZ_TICKET = 1
    BIZ_CARD = 2
    BIZ_THEATER_CARD = 3
    BIZ_CHOICES = [(BIZ_TICKET, '票务订单'), (BIZ_CARD, '会员卡订单'), (BIZ_THEATER_CARD, '剧场会员卡订单')]
    biz = models.SmallIntegerField('业务类型', default=BIZ_TICKET, choices=BIZ_CHOICES)
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)
    dy_pay_config = models.ForeignKey(DouYinPayConfig, verbose_name='抖音支付商户', null=True, blank=True,
                                      on_delete=models.SET_NULL)

    @classmethod
    def create_record(cls, amount, user, pay_type, biz, wx_pay_config=None, dy_pay_config=None):
        return cls.objects.create(amount=amount, user=user, pay_type=pay_type,
                                  biz=biz, wx_pay_config=wx_pay_config, dy_pay_config=dy_pay_config)

    @property
    def pay_client(self):
        return get_mp_pay_client(self.pay_type, self.wx_pay_config)

    @classmethod
    def available_pay_types(self):
        return [self.PAY_WeiXin_LP, self.PAY_WeiXin_MP, self.PAY_WeiXin_APP]

    def __str__(self):
        return u'商户订单号: {}, 金额: {}, 支付方式: {}'.format(self.payno, self.amount, self.get_pay_type_display())

    class Meta:
        verbose_name = verbose_name_plural = u'收款记录'

    @staticmethod
    def autocomplete_search_fields():
        return 'id', 'payno'

    @property
    def paid(self):
        return self.status == self.STATUS_FINISHED

    def biz_paid(self):
        """
        付款成功时,根据业务类型决定处理方法
        :return:
        """
        if self.biz == self.BIZ_TICKET:
            from ticket.models import TicketOrder
            t_order = TicketOrder.objects.filter(receipt_id=self.id).first()
            t_order.set_paid()
        elif self.biz == self.BIZ_CARD:
            m_order = MemberCardRecord.objects.filter(receipt_id=self.id).first()
            m_order.set_paid()
        elif self.biz == self.BIZ_THEATER_CARD:
            tc_order = TheaterCardOrder.objects.filter(receipt_id=self.id).first()
            tc_order.set_paid()
        else:
            log.fatal('unkonw biz: %s, of receipt: %s' % (self.biz, self.pk))

    def set_paid(self, pay_type=ReceiptAbstract.PAY_WeiXin_MP, transaction_id=None):
        if self.paid:
            return
        self.status = self.STATUS_FINISHED
        self.pay_type = pay_type
        self.transaction_id = transaction_id if transaction_id else self.transaction_id
        self.save(update_fields=['status', 'transaction_id'])
        self.biz_paid()
        # for order in self.order_receipt.all():
        #     order.set_paid()
        from mall.signals import receipt_paid_signal
        receipt_paid_signal.send(sender=Receipt, instance=self)

    def get_user_id(self):
        if self.pay_type == self.PAY_WeiXin_MP:
            return self.user.openid
        elif self.pay_type == self.PAY_WeiXin_APP:
            return self.user.app_openid
        elif self.pay_type == self.PAY_WeiXin_LP:
            return self.user.lp_openid
        else:
            log.error('unsupported pay_type: %s' % self.pay_type)
            raise CustomAPIException('不支持的支付类型')

    def get_pay_order_info(self):
        if self.biz == self.BIZ_TICKET:
            return dict(body='票务订单', user_id=self.get_user_id())
        elif self.biz == self.BIZ_CARD:
            return dict(body='会员卡订单', user_id=self.get_user_id())
        elif self.biz == self.BIZ_THEATER_CARD:
            return dict(body='剧场会员卡订单', user_id=self.get_user_id())
        else:
            raise CustomAPIException("order_info_not_set")

    def get_notify_url(self):
        return umf_notify_url if self.pay_type in self.umf_pay_type() else notify_url

    def update_info(self):
        c = get_mp_pay_client(self.pay_type, self.wx_pay_config)
        try:
            res = c.query_order(self)
            if res:
                self.transaction_id = res.get('transaction_id')
                self.save(update_fields=['transaction_id'])
        except WeChatPayException as e:
            log.error(e)


class HotSearch(models.Model):
    name = models.CharField('关键词', max_length=30)
    order_no = models.IntegerField(u'排序号', default=0, help_text=u'越大越前')

    class Meta:
        verbose_name_plural = verbose_name = '热搜词'
        ordering = ['-order_no']

    def __str__(self):
        return self.name


class ServiceAuthRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE)
    TYPE_SERVICE = 1
    TYPE_REALNAME = 2
    TYPE_CHOICES = ((TYPE_SERVICE, '服务协议'), (TYPE_REALNAME, '实名须知'))
    auth_type = models.IntegerField(choices=TYPE_CHOICES, verbose_name='协议类型', default=TYPE_SERVICE)
    create_at = models.DateTimeField('授权时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '用户服务协议记录'

    def __str__(self):
        return str(self.user)

    @classmethod
    def create(cls, user, auth_type):
        inst, _ = cls.objects.get_or_create(user=user, auth_type=auth_type)
        if auth_type == cls.TYPE_SERVICE:
            user.account.agree_service = True
            user.account.save(update_fields=['agree_service'])
        else:
            user.account.agree_name = True
            user.account.save(update_fields=['agree_name'])
        return inst


class MembershipCard(models.Model):
    title = models.CharField('名称', max_length=20)
    amount = models.DecimalField('金额', max_digits=9, decimal_places=2, default=0)
    days = models.IntegerField('有效天数', default=0)
    is_open = models.BooleanField('是否开售', default=False)
    discount = models.DecimalField('折扣', max_digits=9, decimal_places=1, help_text='95表示95折', default=100)
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)
    customer_mobile = models.CharField('客服电话一', max_length=20, null=True, blank=True)
    customer_mobile_s = models.CharField('客服电话二', max_length=20, null=True, blank=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name_plural = verbose_name = '年度会员卡设置'

    def __str__(self):
        return self.title

    @classmethod
    def get(cls):
        return cls.objects.first()


class MembershipImage(models.Model):
    card = models.ForeignKey(MembershipCard, verbose_name='会员卡', on_delete=models.CASCADE)
    image = models.ImageField('图片', upload_to=f'{IMAGE_FIELD_PREFIX}/mall/card',
                              validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = '会员卡详情图'

    def __str__(self):
        return str(self.id)


class CardRecord(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE)
    deadline_at = models.DateField('到期时间', null=True)

    class Meta:
        verbose_name_plural = verbose_name = '用户年度会员卡'

    def __str__(self):
        return str(self.user)

    @classmethod
    def get_inst(cls, user):
        inst, _ = cls.objects.get_or_create(user=user)
        return inst

    def set_deadline(self):
        deadline_at = self.deadline_at if self.deadline_at else timezone.now().date()
        mc = MembershipCard.get()
        if not self.deadline_at:
            # 第一次购买
            from statistical.models import TotalStatistical
            TotalStatistical.change_year_card_stl()
        self.deadline_at = deadline_at + timedelta(days=mc.days)
        self.save(update_fields=['deadline_at'])


class MemberCardRecordManager(Manager):
    """
    filter by role implicitly.
    """

    def get_queryset(self):
        return super().get_queryset().filter(biz=Receipt.BIZ_CARD)


# class MemberCardRecordReceipt(Receipt):
#     objects = MemberCardRecordManager()
#
#     class Meta:
#         proxy = True
#         verbose_name = verbose_name_plural = '年度会员卡订单'
#         ordering = ['-pk']


class MemberCardRecord(models.Model):
    card = models.ForeignKey(CardRecord, verbose_name='会员卡记录', on_delete=models.CASCADE, null=True,
                             related_name='member_record')
    order_no = models.CharField(u'订单号', max_length=128, unique=True, null=True)
    card_agent = models.ForeignKey(User, verbose_name='推荐人(代理)', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='card_agent')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE, null=True)
    mobile = models.CharField('联系电话', max_length=20, null=True)
    u_user_id = models.IntegerField('用户id', default=0, editable=False)
    u_agent_id = models.IntegerField('代理id', default=0, editable=False)
    STATUS_UNPAID = 1
    STATUS_PAID = 2
    STATUS_CHOICES = ((STATUS_UNPAID, u'待付款'), (STATUS_PAID, u'已付款'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_UNPAID)
    ST_DEFAULT = 1
    ST_ADMIN = 2
    ST_CHOICES = ((ST_DEFAULT, U'购买会员卡'), (ST_ADMIN, U'后台授权'))
    source_type = models.IntegerField(u'授权方式', choices=ST_CHOICES, default=ST_DEFAULT)
    amount = models.DecimalField('实付金额', max_digits=9, decimal_places=2, default=0)
    discount = models.DecimalField('折扣', max_digits=9, decimal_places=1, default=100)
    receipt = models.ForeignKey(Receipt, verbose_name=u'收款信息', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='card_receipt')
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    pay_at = models.DateTimeField('付款时间', null=True, blank=True)
    pay_type = models.SmallIntegerField('支付类型', choices=Receipt.PAY_CHOICES, default=Receipt.PAY_NOT_SET)
    transaction_id = models.CharField('微信(抖音)支付单号', max_length=32, null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '年度会员卡订单'
        ordering = ['-pk']

    def __str__(self):
        return self.order_no or str(self.pay_at)

    @classmethod
    def create_record(cls, user, pay_type, mc, source_type=ST_DEFAULT):
        card = CardRecord.get_inst(user)
        receipt = Receipt.create_record(amount=mc.amount, user=user, pay_type=pay_type, biz=Receipt.BIZ_CARD,
                                        wx_pay_config=mc.wx_pay_config)
        agent = user.get_new_parent()
        u_agent_id = 0
        if agent:
            u_agent_id = agent.id
        # if user.new_parent and user.new_parent.account.is_agent():
        #     card_agent = user.new_parent
        #     u_agent_id = user.new_parent.id
        # else:
        #     if user.parent and user.parent.account.is_agent():
        #         card_agent = user.parent
        #         u_agent_id = user.parent.id
        return cls.objects.create(card=card, amount=mc.amount if source_type == cls.ST_DEFAULT else 0, user=user,
                                  u_user_id=user.id, u_agent_id=u_agent_id,
                                  card_agent_id=u_agent_id if u_agent_id > 0 else None,
                                  mobile=user.mobile,
                                  discount=mc.discount, receipt_id=receipt.id, order_no=randomstrwithdatetime_card(),
                                  pay_type=pay_type, source_type=source_type)

    def set_paid(self):
        if self.status in [self.STATUS_UNPAID]:
            self.status = self.STATUS_PAID
            self.pay_at = timezone.now()
            self.transaction_id = self.receipt.transaction_id if self.receipt else None
            self.save(update_fields=['status', 'pay_at', 'transaction_id'])
            self.card.set_deadline()
            self.card_award()

    def send_parent_notice(self, openid, desc):
        from push import MpTemplateClient
        name = '{}({})'.format(self.card.user.get_full_name(), desc)
        MpTemplateClient.order_parent_notice(openid, self.order_no, '会员卡', self.amount, name)

    def card_award(self):
        if self.card_agent and self.card_agent.account.level:
            ratio = self.card_agent.account.level.card_ratio
            if ratio > 0:
                # 会员卡销售奖
                amount = self.amount * ratio / 100
                if amount > 0.01:
                    from shopping_points.models import UserCommissionChangeRecord
                    UserCommissionChangeRecord.add_record(self.card_agent.account, amount,
                                                          UserCommissionChangeRecord.SOURCE_TYPE_CARD, '售卖会员卡获得佣金',
                                                          status=UserCommissionChangeRecord.STATUS_CAN_WITHDRAW,
                                                          card_order=self)
                    if self.card_agent.openid:
                        try:
                            self.send_parent_notice(self.card_agent.openid, '会员卡销售奖{}'.format(amount))
                        except Exception as e:
                            log.error('发送消息失败')


class AgreementRecord(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE)
    agree_member = models.BooleanField('已签署用户协议', default=False)
    agree_privacy = models.BooleanField('已签署隐私政策', default=False)
    agree_agent = models.BooleanField('已开启Ai智能体服务', default=False)
    create_at = models.DateTimeField('授权时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '用户协议隐私记录'

    def __str__(self):
        return str(self.user)

    @classmethod
    def create(cls, user, auth_type):
        agree_key = get_redis_name(f'agree_key_{auth_type}_{user.id}')
        from caches import run_with_lock
        with run_with_lock(agree_key, 2) as got:
            if got:
                auth_type = int(auth_type)
                inst, _ = cls.objects.get_or_create(user=user)
                if auth_type == 1:
                    inst.agree_member = True
                    inst.save(update_fields=['agree_member'])
                    user.agree_member = True
                    user.save(update_fields=['agree_member'])
                elif auth_type == 2:
                    inst.agree_privacy = True
                    inst.save(update_fields=['agree_privacy'])
                    user.agree_privacy = True
                    user.save(update_fields=['agree_privacy'])
                else:
                    inst.agree_agent = True
                    inst.save(update_fields=['agree_agent'])
                    user.agree_agent = True
                    user.save(update_fields=['agree_agent'])


class TheaterCard(models.Model):
    title = models.CharField('名称', max_length=20)
    amount = models.DecimalField('售价', max_digits=9, decimal_places=2, default=0)
    receive_amount = models.DecimalField('到账余额', max_digits=9, decimal_places=2, default=0)
    day_max_num = models.IntegerField('每日最多购买票数', default=4)
    customer_mobile = models.CharField('客服电话一', max_length=20, null=True, blank=True)
    customer_mobile_s = models.CharField('客服电话二', max_length=20, null=True, blank=True)
    is_open = models.BooleanField('是否启用', default=False)
    can_buy = models.BooleanField('是否售卖', default=False)
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name_plural = verbose_name = '剧场会员卡设置'
        ordering = ['-pk']

    def __str__(self):
        return self.title

    def clean(self):
        if self.is_open:
            TheaterCard.objects.filter(is_open=True).exclude(id=self.id).update(is_open=False)
        if self.can_buy:
            TheaterCard.objects.filter(can_buy=True).exclude(id=self.id).update(can_buy=False)

    @classmethod
    def get_inst(cls):
        return cls.objects.filter(is_open=True).first()


class TheaterCardTicketLevel(models.Model):
    card = models.ForeignKey(TheaterCard, verbose_name='剧场会员卡', on_delete=models.CASCADE)
    title = models.CharField('票档描述', max_length=20, help_text='需和场次创建时的票档描述一致')
    discount = models.DecimalField('优惠折扣', max_digits=9, decimal_places=1, default=0)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name_plural = verbose_name = '票档优惠'
        ordering = ['-pk']
        unique_together = ['card', 'title']

    def __str__(self):
        return str(self.id)


class TheaterCardCity(models.Model):
    card = models.ForeignKey(TheaterCard, verbose_name='剧场会员卡', on_delete=models.CASCADE)
    cities = models.ManyToManyField(Division, verbose_name='优惠城市', blank=True, limit_choices_to=models.Q(type=1))
    discount = models.DecimalField('优惠折扣', max_digits=9, decimal_places=1, default=0)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name_plural = verbose_name = '城市优惠'
        ordering = ['-pk']

    def __str__(self):
        return str(self.id)


class TheaterCardImage(models.Model):
    card = models.ForeignKey(TheaterCard, verbose_name='会员卡', on_delete=models.CASCADE)
    image = models.ImageField('图片', upload_to=f'{IMAGE_FIELD_PREFIX}/mall/theatercard',
                              validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = '剧场会员卡详情图'

    def __str__(self):
        return str(self.id)


class TheaterCardUserRecord(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE,
                                related_name='theater_card')
    card_no = models.CharField(u'卡号', max_length=128, unique=True, default=random_theater_card_no, editable=False)
    amount = models.DecimalField('余额', max_digits=9, decimal_places=2, default=0)
    discount_total = models.DecimalField('累计优惠', max_digits=9, decimal_places=2, default=0)
    agent = models.ForeignKey(User, verbose_name='推荐人(代理)', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='theater_first_agent')
    venue = models.ForeignKey('ticket.Venues', verbose_name='演出场馆（门店）', on_delete=models.SET_NULL, null=True,
                              blank=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    is_check_bind = models.BooleanField('是否已首单绑定', default=False)
    version = models.IntegerField('版本', default=0)

    class Meta:
        verbose_name_plural = verbose_name = '用户剧场会员卡'
        ordering = ['-pk']

    def __str__(self):
        return self.card_no

    @classmethod
    def get_inst(cls, user):
        card, _ = cls.objects.get_or_create(user=user)
        return card

    def update_amount(self, amount):
        # 退款和充值，退款和取消订单，退款和购买订单 可能会并发冲突
        from caches import run_with_lock, theater_card_add_amount_key
        key = theater_card_add_amount_key.format(self.id)
        with run_with_lock(key, 2, 2) as got:
            if got:
                self.refresh_from_db(fields=['amount', 'version'])
                if self.__class__.objects.filter(version=self.version,
                                                 pk=self.pk).update(version=F('version') + 1,
                                                                    amount=F('amount') + amount) <= 0:
                    raise Exception('更新用户剧场会员卡余额时版本错误')

    def add_discount_total(self, amount):
        from caches import get_redis, add_discount_total_key
        redis = get_redis()
        redis.lpush(add_discount_total_key, '{}_{}'.format(self.id, float(amount)))

    @classmethod
    def task_add_discount_total(cls):
        from caches import get_redis, add_discount_total_key
        redis = get_redis()
        amount_list = redis.lrange(add_discount_total_key, 0, -1)
        if amount_list:
            data_dict = dict()
            for value in amount_list:
                val = redis.rpop(add_discount_total_key)
                if val:
                    id, amount = val.split('_')
                    key = str(id)
                    if data_dict.get(key):
                        data_dict[key] += float(amount)
                    else:
                        data_dict[key] = float(amount)
            if data_dict:
                for key, value in data_dict.items():
                    inst = cls.objects.filter(id=int(key)).first()
                    if inst:
                        inst.discount_total += Decimal(value)
                        inst.save(update_fields=['discount_total'])


class TheaterCardUserDetail(models.Model):
    user_id = models.IntegerField('用户ID', null=True, editable=False)
    user_card = models.ForeignKey(TheaterCardUserRecord, verbose_name='用户剧场会员卡', on_delete=models.CASCADE)
    card = models.ForeignKey(TheaterCard, verbose_name='剧场会员卡', on_delete=models.CASCADE)
    amount = models.DecimalField('余额', max_digits=9, decimal_places=2, default=0)
    create_at = models.DateTimeField('首次充值时间', null=True)
    charge_at = models.DateTimeField('最新充值时间', null=True)
    version = models.IntegerField('版本', default=0, editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '剧场会员卡用户记录'
        ordering = ['-pk']
        unique_together = ['user_card', 'card']

    def __str__(self):
        return str(self.card)

    @classmethod
    def get_old_cards(cls, user_id):
        qs = cls.objects.filter(user_id=user_id, amount__gt=0).order_by('create_at')
        return qs

    def set_user_id(self):
        if not self.user_id:
            self.user_id = self.user_card.user_id
            self.save(update_fields=['user_id'])

    @classmethod
    def init_record(cls):
        qs = TheaterCardUserRecord.objects.filter(amount__gt=0)
        card = TheaterCard.get_inst()
        for user_card in qs:
            tc_order_qs = TheaterCardOrder.objects.filter(user=user_card.user, status=TheaterCardOrder.STATUS_PAID)
            create_at = timezone.now()
            charge_at = timezone.now()
            if tc_order_qs:
                tc_f = tc_order_qs.first()
                tc_l = tc_order_qs.last()
                create_at = tc_f.pay_at
                charge_at = tc_l.pay_at
            cls.objects.update_or_create(user_id=user_card.user_id, user_card=user_card, card=card,
                                         defaults=dict(amount=user_card.amount, create_at=create_at,
                                                       charge_at=charge_at))

    @classmethod
    def get_inst(cls, user_card: TheaterCardUserRecord, card: TheaterCard):
        inst = cls.objects.filter(user_card=user_card, card=card).first()
        return inst

    @classmethod
    def create_record(cls, user_card: TheaterCardUserRecord, card: TheaterCard):
        # 首次充值
        now = timezone.now()
        inst = cls.objects.create(user_id=user_card.user_id, user_card=user_card, card=card, create_at=now,
                                  charge_at=now)
        return inst

    def update_amount(self, amount, is_charge=False):
        # 使用和再充值
        # 退款和充值，退款和取消订单，退款和购买订单 可能会并发冲突
        from caches import run_with_lock, theater_card_detail_add_amount_key
        key = theater_card_detail_add_amount_key.format(self.id)
        with run_with_lock(key, 2, 2) as got:
            if got:
                self.refresh_from_db(fields=['amount', 'version'])
                qs = self.__class__.objects.filter(version=self.version, pk=self.pk)
                if is_charge:
                    ret = qs.update(version=F('version') + 1, amount=F('amount') + amount, charge_at=timezone.now())
                else:
                    ret = qs.update(version=F('version') + 1, amount=F('amount') + amount)
                if ret <= 0:
                    raise Exception('更新用户剧场会员卡余额时版本错误')


class TheaterCardUserBuy(models.Model):
    card = models.ForeignKey(TheaterCardUserRecord, verbose_name='用户剧场会员卡', on_delete=models.CASCADE)
    user_id = models.IntegerField('用户ID')
    num = models.IntegerField('购买次数', default=0)
    create_at = models.DateField('创建时间')

    class Meta:
        verbose_name_plural = verbose_name = '用户购票统计'
        ordering = ['-pk']
        unique_together = ['card', 'create_at']

    def __str__(self):
        return str(self.create_at)

    @classmethod
    def get_inst(cls, card, create_at=None):
        if not create_at:
            create_at = timezone.now().date()
        inst = cls.objects.filter(card=card, create_at=create_at).first()
        return inst

    @classmethod
    def create_record(cls, card, create_at=None):
        if not create_at:
            create_at = timezone.now().date()
        inst, _ = cls.objects.get_or_create(card=card, user_id=card.user.id, create_at=create_at)
        return inst

    def change_num(self, num):
        self.num += num
        self.save(update_fields=['num'])


class TheaterCardOrder(models.Model):
    card = models.ForeignKey(TheaterCard, verbose_name='剧场会员卡', on_delete=models.CASCADE)
    card_no = models.CharField(u'用户剧场会员卡号', max_length=128)
    order_no = models.CharField(u'订单号', max_length=128, unique=True, default=random_theater_order_no)
    user = models.ForeignKey(User, verbose_name='用户', on_delete=models.CASCADE)
    mobile = models.CharField('手机号', max_length=20, null=True)
    agent = models.ForeignKey(User, verbose_name='推荐人(代理)', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='theater_card_agent')
    venue = models.ForeignKey('ticket.Venues', verbose_name='演出场馆（门店）', on_delete=models.SET_NULL, null=True,
                              blank=True)
    u_user_id = models.IntegerField('用户id', default=0, editable=False)
    u_agent_id = models.IntegerField('代理id', default=0, editable=False)
    amount = models.DecimalField('实付金额', max_digits=9, decimal_places=2, default=0)
    receive_amount = models.DecimalField('到账余额', max_digits=9, decimal_places=2, default=0)
    STATUS_UNPAID = 1
    STATUS_PAID = 2
    STATUS_CHOICES = ((STATUS_UNPAID, u'待付款'), (STATUS_PAID, u'已付款'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_UNPAID)
    pay_type = models.SmallIntegerField('支付类型', choices=Receipt.PAY_CHOICES, default=Receipt.PAY_NOT_SET)
    receipt = models.ForeignKey(Receipt, verbose_name=u'收款信息', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='theater_card_receipt')
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    pay_at = models.DateTimeField('付款时间', null=True, blank=True)
    transaction_id = models.CharField('微信(抖音)支付单号', max_length=32, null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '剧场会员卡订单'
        ordering = ['-pk']

    def __str__(self):
        return self.order_no

    @classmethod
    def create_record(cls, user, card, pay_type):
        agent = user.get_new_parent()
        venue = agent.account.promote_venue if agent else None
        user_card = TheaterCardUserRecord.get_inst(user)
        receipt = Receipt.create_record(amount=card.amount, user=user, pay_type=pay_type, biz=Receipt.BIZ_THEATER_CARD,
                                        wx_pay_config=card.wx_pay_config)
        u_agent_id = agent.id if agent else 0
        return cls.objects.create(card=card, card_no=user_card.card_no, user_id=user.id, agent=agent,
                                  mobile=user.mobile,
                                  venue=venue, receive_amount=card.receive_amount,
                                  u_user_id=user.id, u_agent_id=u_agent_id, amount=card.amount, receipt=receipt,
                                  pay_type=pay_type)

    def set_paid(self):
        if self.status in [self.STATUS_UNPAID]:
            self.status = self.STATUS_PAID
            self.pay_at = timezone.now()
            self.transaction_id = self.receipt.transaction_id
            self.save(update_fields=['status', 'pay_at', 'transaction_id'])
            try:
                self.charge_amount()
            except Exception as e:
                log.error(e)
            try:
                self.card_award()
            except Exception as e:
                log.error('发放剧场会员卡奖励失败，{}'.format(self.order_no))

    def charge_amount(self):
        user_card = TheaterCardUserRecord.get_inst(self.user)
        card_num = 0
        if not user_card.is_check_bind:
            user_card.is_check_bind = True
            user_card.agent = self.agent
            user_card.venue = self.venue
            user_card.save(update_fields=['is_check_bind', 'agent', 'venue'])
            card_num = 1
        # 购买会员卡不存在并发
        TheaterCardChangeRecord.add_record(user=self.user, source_type=TheaterCardChangeRecord.SOURCE_TYPE_CHARGE,
                                           amount=self.receive_amount,
                                           card_order_no=self.order_no, card=self.card, is_charge=True)
        from statistical.models import TotalStatistical
        TotalStatistical.change_super_card_stl(order_num=1, card_num=card_num, amount=self.amount,
                                               rest_amount=self.receive_amount)

    def send_parent_notice(self, openid, desc):
        from push import MpTemplateClient
        name = '{}({})'.format(self.user.get_full_name(), desc)
        MpTemplateClient.order_parent_notice(openid, self.order_no, '剧场会员卡', self.amount, name)

    def card_award(self):
        if self.agent and self.agent.account.level:
            ratio = self.agent.account.level.theater_ratio
            if ratio > 0:
                # 剧场会员卡分销比率
                amount = self.amount * ratio / 100
                if amount > 0.01:
                    from shopping_points.models import UserCommissionChangeRecord
                    UserCommissionChangeRecord.add_record(self.agent.account, amount,
                                                          UserCommissionChangeRecord.SOURCE_TYPE_THEATER_CARD,
                                                          '售卖剧场会员卡获得佣金',
                                                          status=UserCommissionChangeRecord.STATUS_CAN_WITHDRAW,
                                                          theater_order=self)
                    try:
                        self.send_parent_notice(self.agent.openid, '剧场会员卡销售奖{}'.format(amount))
                    except Exception as e:
                        log.error('发送消息失败')


class TheaterCardChangeRecord(models.Model):
    user = models.ForeignKey(User, verbose_name='用户', on_delete=models.CASCADE)
    SOURCE_TYPE_CHARGE = 1
    SOURCE_TYPE_CONSUME = 2
    SOURCE_TYPE_CANCEL = 3
    SOURCE_TYPE_REFUND = 4
    SOURCE_TYPE_CHOICES = (
        (SOURCE_TYPE_CHARGE, '开通/续费会员卡'), (SOURCE_TYPE_CONSUME, '优惠购票'), (SOURCE_TYPE_CANCEL, '取消订单返还'),
        (SOURCE_TYPE_REFUND, '退款返还'))
    amount = models.DecimalField('数额', default=0, max_digits=15, decimal_places=2)
    after_amount = models.DecimalField('结算后卡余额', default=0, max_digits=15, decimal_places=2)
    source_type = models.IntegerField(choices=SOURCE_TYPE_CHOICES, verbose_name='类型', default=SOURCE_TYPE_CHARGE)
    card_order_no = models.CharField(u'剧场会员卡订单号', max_length=128, null=True, blank=True)
    ticket_order = models.ForeignKey('ticket.TicketOrder', verbose_name='票务订单', null=True, blank=True,
                                     on_delete=models.SET_NULL)
    create_at = models.DateTimeField(u'创建时间', auto_now_add=True, editable=True)

    class Meta:
        verbose_name = '剧场会员卡余额明细'
        verbose_name_plural = verbose_name
        ordering = ['-pk']

    @classmethod
    @atomic
    def add_record(cls, user, source_type, amount, ticket_order=None, card_order_no=None, card=None, is_charge=False):
        user_card = TheaterCardUserRecord.get_inst(user)
        after_amount = user_card.amount + amount
        # 退款和购票如果一起可能会并发
        r = cls.objects.create(user=user, source_type=source_type, amount=amount, after_amount=after_amount,
                               ticket_order=ticket_order, card_order_no=card_order_no)
        # user_card = TheaterCardUserRecord.get_inst(user)
        user_card.update_amount(amount)
        if amount > 0:
            if not card:
                card = TheaterCard.get_inst()
            card_detail = TheaterCardUserDetail.get_inst(user_card, card)
            if not card_detail:
                card_detail = TheaterCardUserDetail.create_record(user_card, card)
            TheaterCardChangeRecordDetail.charge_record(r, card_detail, amount, is_charge=is_charge)
        else:
            # 扣减明细,
            TheaterCardChangeRecordDetail.use_record(r, user_card, -amount)
        return r


class TheaterCardChangeRecordDetail(models.Model):
    record = models.ForeignKey(TheaterCardChangeRecord, verbose_name='剧场会员卡余额明细', on_delete=models.CASCADE)
    card_detail = models.ForeignKey(TheaterCardUserDetail, verbose_name='剧场会员卡', on_delete=models.CASCADE)
    amount = models.DecimalField('数额', default=0, max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = '剧场会员卡余扣款明细'
        verbose_name_plural = verbose_name
        ordering = ['-pk']
        unique_together = ['record', 'card_detail']

    @classmethod
    def charge_record(cls, record: TheaterCardChangeRecord, card_detail: TheaterCardUserDetail, amount,
                      is_charge=False):
        r = cls.objects.create(record=record, card_detail=card_detail, amount=amount)
        card_detail.update_amount(r.amount, is_charge=is_charge)

    @classmethod
    def use_record(cls, record: TheaterCardChangeRecord, user_card: TheaterCardUserRecord, amount):
        tc_detail_qs = TheaterCardUserDetail.objects.filter(user_card_id=user_card.id, amount__gt=0).order_by(
            'charge_at')
        is_break = False
        for card_detail in tc_detail_qs:
            if card_detail.amount >= amount:
                m_amount = amount
                is_break = True
            else:
                m_amount = card_detail.amount
            r = cls.objects.create(record=record, card_detail=card_detail, amount=-m_amount)
            card_detail.update_amount(r.amount)
            if is_break:
                break
            else:
                # r.amount 是负数。扣减
                amount = amount + r.amount


class UserAddress(DateDetailAbstract):
    user = models.ForeignKey(User, verbose_name='用户', related_name='user_address', on_delete=models.CASCADE)
    province = models.CharField(u'省', null=True, max_length=30, help_text=u'省', blank=True)
    city = models.CharField(u'市', null=True, max_length=30, help_text=u'市', blank=True)
    county = models.CharField(u'区/县', null=True, max_length=30, help_text=u'区/县', blank=True)
    street = models.CharField(u'街道', null=True, max_length=30, help_text='外部供应链需要,京东天猫', blank=True)
    address = models.CharField(u'详细地址', null=True, max_length=1024, blank=True)
    phone = models.CharField(u'手机号码', max_length=20)
    receive_name = models.CharField('收货人姓名', max_length=30)
    default = models.BooleanField('默认地址', default=False)

    class Meta:
        verbose_name_plural = verbose_name = '用户地址'
        ordering = ['-pk']

    def __str__(self):
        return '%s: %s' % (self.receive_name, self.address[0:10])

    @property
    def division(self):
        return Division(province=self.province, city=self.city, county=self.county)

    @property
    def to_express_address(self):
        """
        存为 省#市#区#地址#收件人, 用于订单导出发货单时使用
        :return:
        """
        return '#'.join([self.province, self.city, self.county, self.address, self.receive_name])

    @property
    def to_express_address_new(self):
        """
        存为 省#市#区#地址, 用于订单导出发货单时使用
        :return:
        """
        return '#'.join([self.province, self.city, self.county, self.address])
