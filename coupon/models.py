# coding=utf-8
from __future__ import unicode_literals
from django.db import models
from django.utils import timezone
from django.conf import settings
from restframework_ext.models import UseNoAbstract
from ticket.models import ShowProject, ShowType, TicketOrder
from caches import get_pika_redis, get_redis_name
import uuid


class Coupon(UseNoAbstract):
    name = models.CharField('名称', max_length=128)
    amount = models.DecimalField(u'减免金额', max_digits=13, decimal_places=2, default=0)
    expire_time = models.DateTimeField('使用截止时间')
    user_tips = models.TextField('使用提示', help_text='提示使用范围等')
    STATUS_ON = 2
    STATUS_OFF = 1
    STATUS_CHOICES = ((STATUS_ON, u'上架'), (STATUS_OFF, u'下架'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_OFF)
    off_use = models.BooleanField('下架后是否可继续使用', default=True)
    user_obtain_limit = models.IntegerField('用户限领次数', default=0, help_text='0为不限次数')
    require_amount = models.DecimalField(u'使用满足金额', max_digits=13, decimal_places=2, default=0)
    shows = models.ManyToManyField(ShowProject, verbose_name='可使用的演出项目', related_name='shows', blank=True)
    limit_show_types = models.ManyToManyField(ShowType, verbose_name='可使用演出类型', related_name='show_types', blank=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name_plural = verbose_name = '消费券'

    def __str__(self):
        return self.name

    @classmethod
    def auto_off_task(cls):
        """
        自动下架
        """
        cls.objects.filter(status=cls.STATUS_ON, expire_time__lte=timezone.now()).update(status=cls.STATUS_OFF)

    def check_can_use(self):
        st = True
        if self.status == self.STATUS_OFF and not self.off_use:
            st = False
        return st


class UserCouponRecord(UseNoAbstract):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', related_name='coupons',
                             on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, verbose_name='优惠券', on_delete=models.CASCADE)
    STATUS_DEFAULT = 1
    STATUS_USE = 2
    STATUS_EXPIRE = 3
    STATUS_CHOICES = ((STATUS_DEFAULT, u'未使用'), (STATUS_USE, u'已使用'), (STATUS_EXPIRE, u'已过期'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_DEFAULT)
    expire_time = models.DateTimeField('使用截止时间')
    require_amount = models.DecimalField(u'使用满足金额', max_digits=13, decimal_places=2, default=0)
    used_time = models.DateTimeField('使用时间', null=True, blank=True)
    create_at = models.DateTimeField('领取时间', auto_now_add=True)
    order = models.ForeignKey(TicketOrder, verbose_name='使用订单', null=True, blank=True, on_delete=models.SET_NULL)
    snapshot = models.TextField('优惠券快照', null=True, blank=True, help_text='领取时保存的快照', editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '用户优惠券记录'

    def __str__(self):
        return '{}:{}'.format(self.user, self.coupon)

    def save_common(self):
        fields = ['snapshot']
        self.snapshot = self.get_snapshot()
        self.save(update_fields=fields)

    @classmethod
    def check_expire_task(cls):
        """
        自动过期任务
        """
        cls.objects.filter(status=cls.STATUS_DEFAULT, expire_time__lte=timezone.now()).update(status=cls.STATUS_EXPIRE)

    @classmethod
    def user_obtain_key(cls, coupon_no: str, user_id: int):
        key = get_redis_name('coupon{}'.format(coupon_no))
        name = get_redis_name('user{}'.format(user_id))
        return key, name

    @classmethod
    def user_obtain_cache(cls, coupon_no: str, user_id: int) -> int:
        key, name = cls.user_obtain_key(coupon_no, user_id)
        with get_pika_redis() as redis:
            num = redis.hget(key, name) or 0
        return int(num)

    def get_snapshot(self):
        import json
        """
        消费券快照
        :return:
        """
        coupon = self.coupon
        shows_ids = []
        shows_names = []
        show_types_ids = []
        show_types_names = []
        for show in coupon.shows.all():
            shows_ids.append(show.no)
            shows_names.append(show.name)
        for f in coupon.limit_show_types.all():
            show_types_ids.append(f.id)
            show_types_names.append(f.name)
        data = dict(name=coupon.name, no=coupon.no, amount=float(coupon.amount),
                    user_obtain_limit=coupon.user_obtain_limit,
                    shows_nos=shows_ids, shows_names=shows_names, show_types_ids=show_types_ids,
                    show_types_names=show_types_names, user_tips=coupon.user_tips)
        return json.dumps(data)
