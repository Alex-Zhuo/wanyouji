# coding=utf-8
from __future__ import unicode_literals

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.conf import settings

from common.config import FILE_FIELD_PREFIX
from restframework_ext.models import UseNoAbstract
from ticket.models import ShowProject, ShowType, TicketOrder, ShowContentCategorySecond
from caches import get_pika_redis, get_redis_name
import json
import logging
from django.db import close_old_connections
log = logging.getLogger(__name__)


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
    shows = models.ManyToManyField(ShowProject, verbose_name='可使用的节目', related_name='shows', blank=True)
    limit_show_types_second = models.ManyToManyField(ShowContentCategorySecond, verbose_name='可使用节目分类',
                                                     related_name='show_types_second', blank=True)
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
    order = models.OneToOneField(TicketOrder, verbose_name='使用订单', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='coupon_order')
    snapshot = models.TextField('优惠券快照', null=True, blank=True, help_text='领取时保存的快照', editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '用户消费券记录'

    def __str__(self):
        return '{}:{}'.format(self.user, self.coupon)

    @property
    def can_use(self):
        return self.status == self.STATUS_DEFAULT and self.expire_time > timezone.now()

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
        for f in coupon.limit_show_types_second.all():
            show_types_ids.append(f.id)
            show_types_names.append(f.name)
        data = dict(name=coupon.name, no=coupon.no, amount=float(coupon.amount),
                    user_obtain_limit=coupon.user_obtain_limit,
                    shows_nos=shows_ids, shows_names=shows_names, show_types_second_ids=show_types_ids,
                    show_types_names=show_types_names, user_tips=coupon.user_tips)
        return json.dumps(data)

    def check_can_show_use(self, show: ShowProject):
        snapshot = json.loads(self.snapshot)
        limit_show_types_second_ids = snapshot['show_types_second_ids']
        limit_shows_nos = snapshot['shows_nos']
        can_use = False
        if not (limit_show_types_second_ids and show.cate_second.id not in limit_show_types_second_ids):
            can_use = True
        if not can_use and not (limit_shows_nos and show.no not in limit_shows_nos):
            can_use = True
        return can_use

    def set_use(self, order):
        self.order = order
        self.status = self.STATUS_USE
        self.used_time = timezone.now()
        self.save(update_fields=['used_time', 'order', 'status'])

    def cancel_use(self):
        self.order = None
        self.status = self.STATUS_DEFAULT if self.expire_time < timezone.now() else self.STATUS_EXPIRE
        self.used_time = None
        self.save(update_fields=['used_time', 'order', 'status'])


class UserCouponImport(models.Model):
    file = models.FileField(u'文件', upload_to=f'{FILE_FIELD_PREFIX}/coupon',
                            validators=[FileExtensionValidator(allowed_extensions=['xlsx'])], help_text='只支持xlsx')
    remark = models.CharField('备注说明', max_length=100, null=True, blank=True)
    ST_NEED = 1
    ST_DOING = 2
    ST_FINISH = 3
    ST_FAIL = 4
    status = models.PositiveIntegerField('状态', default=1,
                                         choices=[(ST_NEED, '未执行'), (ST_DOING, '执行中'), (ST_FINISH, '已完成'),
                                                  (ST_FAIL, '异常')])
    create_at = models.DateTimeField(u'创建时间', auto_now_add=True)
    exec_at = models.DateTimeField(u'执行发放时间', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='操作人员', on_delete=models.CASCADE)
    total_num = models.IntegerField('总行数', default=0)
    success_num = models.IntegerField('成功行数', default=0)
    fail_num = models.IntegerField('失败行数', default=0)
    fail_msg = models.TextField('失败行信息', null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = u'批量发放记录'
        ordering = ['-pk']

    def __str__(self):
        return self.file.name

    @classmethod
    def do_coupon_import_task(cls, pk):
        close_old_connections()
        inst = cls.objects.get(pk=pk)
        inst.do_import()

    def do_import(self):
        def format_str(content: str):
            return content.replace('_x000D_', ' ')

        self.exec_at = timezone.now()
        self.status = self.ST_DOING
        self.save(update_fields=['status', 'exec_at'])
        fail_num = 0
        success_num = 0
        fail_msg = ''
        try:
            from openpyxl import load_workbook
            wb = load_workbook(self.file.path)
            # wb = load_workbook('d:/11.xlsx')
            ws = wb.active
            update_list = []
            coupon_dict = dict()
            user_dict = dict()
            for line, row in enumerate(ws.rows, 1):
                if line == 1:
                    title_list = [t.value for t in row]
                    mobile_index = title_list.index('手机号')
                    coupon_index = title_list.index('消费券编号')
                    num_index = title_list.index('发放数量')
                    continue
                try:
                    dd = list(map(lambda cell: cell.value, row))
                    mobile = format_str(str(dd[mobile_index]))
                    from common.utils import validate_mobile
                    vm = validate_mobile(mobile)
                    if not vm:
                        raise ValueError('手机号格式错误')
                    if not user_dict.get(mobile):
                        from mall.models import User
                        user = User.objects.filter(mobile=mobile).first()
                        user_dict[mobile] = user
                    else:
                        user = user_dict[mobile]
                    coupon_no = format_str(str(dd[coupon_index]))
                    num = int(dd[num_index])
                    if not coupon_dict.get(coupon_no):
                        coupon = Coupon.objects.get(no=coupon_no)
                        coupon_dict[coupon_no] = coupon
                    else:
                        coupon = coupon_dict[coupon_no]
                    if not user:
                        obj = UserCouponCacheRecord.get_obj(self.id, mobile, coupon.id)
                        obj.num = num
                        update_list.append(obj)
                    else:
                        for i in list(range(0, num)):
                            inst = UserCouponRecord.objects.create(user=user, coupon=coupon,
                                                                   expire_time=coupon.expire_time)
                            inst.save_common()
                    success_num += 1
                except Exception as e:
                    fail_num += 1
                    fail_msg = fail_msg + '{}行,'.format(line)
                    print(e)
            if update_list:
                UserCouponCacheRecord.objects.bulk_update(update_list, ['num'])
        except Exception as e:
            log.error(e)
            fail_msg = str(e)
        self.status = self.ST_FINISH if fail_num == 0 and not fail_msg else self.ST_FAIL
        self.fail_num = fail_num
        self.success_num = success_num
        self.fail_msg = fail_msg
        self.save(update_fields=['status', 'fail_num', 'success_num', 'fail_msg'])


class UserCouponCacheRecord(models.Model):
    record = models.ForeignKey(UserCouponImport, verbose_name='批量发放记录', on_delete=models.SET_NULL, null=True)
    mobile = models.CharField('手机号', max_length=20, db_index=True)
    coupon = models.ForeignKey(Coupon, verbose_name='优惠券', on_delete=models.CASCADE)
    num = models.PositiveSmallIntegerField('发放数量', default=0)

    class Meta:
        verbose_name_plural = verbose_name = '未领取记录'
        ordering = ['-pk']

    @classmethod
    def get_obj(cls, record_id: int, mobile: str, coupon_id: int):
        obj, _ = cls.objects.get_or_create(record_id=record_id, mobile=mobile, coupon_id=coupon_id)
        return obj

    @classmethod
    def do_bind_user_task(cls, mobile: str, user_id: int):
        qs = cls.objects.filter(mobile=mobile)
        for obj in qs:
            coupon = obj.coupon
            for i in list(range(0, obj.num)):
                inst = UserCouponRecord.objects.create(user_id=user_id, coupon=coupon,
                                                       expire_time=coupon.expire_time)
                inst.save_common()
        qs.delete()
