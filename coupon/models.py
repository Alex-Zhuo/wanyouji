# coding=utf-8
from __future__ import unicode_literals

from django.core.validators import FileExtensionValidator, validate_image_file_extension
from django.db import models
from django.utils import timezone
from django.conf import settings

from common.config import FILE_FIELD_PREFIX, IMAGE_FIELD_PREFIX
from restframework_ext.models import UseNoAbstract
from ticket.models import ShowProject, ShowType, TicketOrder, ShowContentCategorySecond, SessionInfo
from caches import get_pika_redis, get_redis_name
import json
import logging
from django.db import close_old_connections
from decimal import Decimal
from common.utils import quantize, get_short_no
from django.core.exceptions import ValidationError

log = logging.getLogger(__name__)


class CouponBasic(models.Model):
    image = models.ImageField('弹窗图片', upload_to=f'{IMAGE_FIELD_PREFIX}/coupon/basic',
                              validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = '消费券配置'

    @classmethod
    def get(cls):
        return cls.objects.first()


class Coupon(UseNoAbstract):
    TYPE_MONEY_OFF = 1
    TYPE_MONEY_DISCOUNT = 2
    TYPE_NUM_DISCOUNT = 3
    COUPON_TYPE_CHOICES = ((TYPE_MONEY_OFF, '满额减券'), (TYPE_MONEY_DISCOUNT, '满额打折券'), (TYPE_NUM_DISCOUNT, '满张(套)数打折券'))
    name = models.CharField('名称', max_length=128)
    type = models.PositiveSmallIntegerField('优惠类型', choices=COUPON_TYPE_CHOICES, default=TYPE_MONEY_OFF)
    SR_FREE = 1
    SR_PAY = 2
    SOURCE_TYPE_CHOICES = ((SR_FREE, '免费领取'), (SR_PAY, '付费购买'))
    source_type = models.PositiveSmallIntegerField('消费券类型', choices=SOURCE_TYPE_CHOICES, default=SR_FREE)
    amount = models.DecimalField('减免金额', max_digits=13, decimal_places=2, default=0)
    pay_amount = models.DecimalField('消费券价格', max_digits=13, decimal_places=2, default=0)
    discount = models.PositiveSmallIntegerField('打折比率', default=0, help_text='80为打8折')
    require_amount = models.DecimalField('使用满足金额', max_digits=13, decimal_places=2, default=0, help_text='满减券、满额打折券必填')
    require_num = models.PositiveSmallIntegerField('使用满足张(套)数', default=0, help_text='满张(套)数打折券必填')
    expire_time = models.DateTimeField('使用截止时间')
    user_tips = models.TextField('使用提示', help_text='提示使用范围等')
    STATUS_ON = 2
    STATUS_OFF = 1
    STATUS_CHOICES = ((STATUS_ON, '上架'), (STATUS_OFF, '下架'))
    status = models.IntegerField('状态', choices=STATUS_CHOICES, default=STATUS_OFF)
    off_use = models.BooleanField('下架后是否可继续使用', default=True)
    stock = models.IntegerField('库存数量', default=0)
    user_obtain_limit = models.IntegerField('用户限领(购)次数', default=0, help_text='0为不限次数')
    shows = models.ManyToManyField(ShowProject, verbose_name='可使用的节目', related_name='shows', blank=True)
    limit_show_types_second = models.ManyToManyField(ShowContentCategorySecond, verbose_name='可使用节目分类',
                                                     related_name='show_types_second', blank=True, editable=False)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name_plural = verbose_name = '消费券'

    def __str__(self):
        return self.name

    def clean(self):
        if self.type == self.TYPE_MONEY_OFF:
            if self.amount <= 0:
                raise ValidationError('减免金额必须大于0')
        elif self.type in [self.TYPE_MONEY_DISCOUNT, self.TYPE_NUM_DISCOUNT]:
            if self.discount <= 0:
                raise ValidationError('打折比率必须大于0')

    @property
    def need_buy(self):
        return self.pay_amount > 0 and self.source_type == self.SR_PAY

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

    @classmethod
    def amount_type(cls):
        # 满额类型
        return [cls.TYPE_MONEY_OFF, cls.TYPE_MONEY_DISCOUNT]

    @classmethod
    def mul_type(cls):
        # 满张类型
        return [cls.TYPE_NUM_DISCOUNT]

    @classmethod
    def discount_type(cls):
        # 打折类型
        return [cls.TYPE_NUM_DISCOUNT, cls.TYPE_MONEY_DISCOUNT]

    @classmethod
    def pop_up_key(cls, user_id: int):
        key = get_redis_name('cp_pop_up')
        name = get_redis_name(str(user_id))
        return key, name

    @classmethod
    def set_pop_up(cls, user_id: int):
        key, name = cls.pop_up_key(user_id)
        with get_pika_redis() as pika:
            pika.hset(key, name, 1)

    @classmethod
    def get_pop_up(cls, user_id: int):
        key, name = cls.pop_up_key(user_id)
        with get_pika_redis() as pika:
            return pika.hget(key, name)

    @classmethod
    def del_pop_up(cls):
        key = get_redis_name('cp_pop_up')
        with get_pika_redis() as pika:
            pika.delete(key)

    @classmethod
    def coupon_update_stock_from_redis(cls):
        close_old_connections()
        from coupon.stock_updater import csc
        csc.persist()

    def coupon_change_stock(self, mul):
        ret = True
        coupon_upd = []
        coupon_upd.append((self.pk, mul, 0))
        from coupon.stock_updater import csc
        succ1, tfc_result = csc.batch_incr(coupon_upd)
        if succ1:
            csc.batch_record_update_ts(csc.resolve_ids(tfc_result))
        else:
            log.warning(f"ticket_levels incr failed")
            # 库存不足
            ret = False
        return ret

    def coupon_redis_stock(self, stock=None):
        # 初始化库存
        from coupon.stock_updater import csc, StockModel
        if stock == None:
            stock = self.stock
        csc.append_cache(StockModel(_id=self.id, stock=stock))

    def coupon_del_redis_stock(self):
        from coupon.stock_updater import csc
        csc.remove(self.id)


class UserCouponRecord(UseNoAbstract):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', related_name='coupons',
                             on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, verbose_name='优惠券', on_delete=models.CASCADE)
    coupon_type = models.PositiveSmallIntegerField('优惠卷类型', choices=Coupon.COUPON_TYPE_CHOICES,
                                                   default=Coupon.TYPE_MONEY_OFF)
    STATUS_DEFAULT = 1
    STATUS_USE = 2
    STATUS_EXPIRE = 3
    STATUS_CHOICES = ((STATUS_DEFAULT, u'未使用'), (STATUS_USE, u'已使用'), (STATUS_EXPIRE, u'已过期'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_DEFAULT)
    expire_time = models.DateTimeField('使用截止时间')
    amount = models.DecimalField(u'减免金额', max_digits=13, decimal_places=2, default=0)
    discount = models.PositiveSmallIntegerField('打折比率', default=0, help_text='80为打8折')
    require_amount = models.DecimalField('使用满足金额', max_digits=13, decimal_places=2, default=0, help_text='满减券、满额打折券必填')
    require_num = models.PositiveSmallIntegerField('使用满足张数', default=0, help_text='满张数打折券必填')
    used_time = models.DateTimeField('使用时间', null=True, blank=True)
    create_at = models.DateTimeField('领取时间', auto_now_add=True)
    order = models.OneToOneField(TicketOrder, verbose_name='使用订单', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='coupon_order')
    snapshot = models.TextField('优惠券快照', null=True, blank=True, help_text='领取时保存的快照', editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '用户消费券记录'

    def __str__(self):
        return '{}:{}'.format(self.user, self.coupon)

    @classmethod
    def create_record(cls, user_id: int, coupon):
        obj = cls.objects.create(user_id=user_id, coupon=coupon, expire_time=coupon.expire_time, amount=coupon.amount,
                                 discount=coupon.discount, coupon_type=coupon.type,
                                 require_amount=coupon.require_amount, require_num=coupon.require_num)
        obj.save_common()
        try:
            Coupon.set_pop_up(user_id)
        except Exception as e:
            log.error(e)
        return obj

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
            shows_names.append(show.title)
        # for f in coupon.limit_show_types_second.all():
        #     show_types_ids.append(f.id)
        #     show_types_names.append(f.name)
        data = dict(name=coupon.name, no=coupon.no, amount=float(coupon.amount),
                    user_obtain_limit=coupon.user_obtain_limit,
                    shows_nos=shows_ids, shows_names=shows_names, show_types_second_ids=show_types_ids,
                    show_types_names=show_types_names, user_tips=coupon.user_tips)
        return json.dumps(data)

    def check_can_show_use(self, show: ShowProject):
        # snapshot = json.loads(self.snapshot)
        # limit_show_types_second_ids = snapshot['show_types_second_ids']
        # limit_shows_nos = snapshot['shows_nos']
        # can_use = False
        # if not (limit_show_types_second_ids and show.cate_second.id not in limit_show_types_second_ids):
        #     can_use = True
        # if not can_use and not (limit_shows_nos and show.no not in limit_shows_nos):
        #     can_use = True
        can_use = True
        shows = self.coupon.shows.all()
        # show_types = self.coupon.limit_show_types_second.all()
        # if show_types and not show_types.filter(id=show.cate_second.id).exists():
        #     can_use = False
        if shows and not shows.filter(id=show.id).exists():
            can_use = False
        return can_use

    def check_type_use(self, amount: Decimal = 0, multiply: int = 0):
        can_use = True
        if self.coupon_type in Coupon.amount_type():
            if amount < self.require_amount:
                can_use = False
        elif self.coupon_type in Coupon.mul_type():
            if multiply < self.require_num:
                can_use = False
        return can_use

    def coupon_check_can_use(self, show: ShowProject, amount: Decimal = 0, multiply: int = 0):
        # snapshot = json.loads(self.snapshot)
        # limit_show_types_second_ids = snapshot['show_types_second_ids']
        # limit_shows_nos = snapshot['shows_nos']
        # can_use = False
        # if not (limit_show_types_second_ids and show.cate_second.id not in limit_show_types_second_ids):
        #     can_use = True
        # if not can_use and not (limit_shows_nos and show.no not in limit_shows_nos):
        #     can_use = True
        can_use = self.check_type_use(amount, multiply)
        if not can_use:
            return can_use
        shows = self.coupon.shows.all()
        # show_types = self.coupon.limit_show_types_second.all()
        # if show_types and not show_types.filter(id=show.cate_second.id).exists():
        #     can_use = False
        if shows and not shows.filter(id=show.id).exists():
            can_use = False
        return can_use

    def set_use(self, order):
        self.order = order
        self.status = self.STATUS_USE
        self.used_time = timezone.now()
        self.save(update_fields=['used_time', 'order', 'status'])

    def cancel_use(self):
        self.order = None
        self.status = self.STATUS_DEFAULT if self.expire_time > timezone.now() else self.STATUS_EXPIRE
        self.used_time = None
        self.save(update_fields=['used_time', 'order', 'status'])

    def get_promote_amount(self, actual_amount, multiply):
        can_use = self.check_type_use(actual_amount, multiply)
        promote_amount = Decimal('0')
        if can_use:
            if self.coupon_type in Coupon.discount_type():
                promote_amount = actual_amount * (100 - self.discount) / 100
            elif self.coupon_type == Coupon.TYPE_MONEY_OFF:
                promote_amount = self.amount
        return quantize(Decimal(promote_amount), 2) if promote_amount > 0 else promote_amount


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
        log.info(f'批量发放记录导入完成,{pk}')

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
                            UserCouponRecord.create_record(user.id, coupon)
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
                UserCouponRecord.create_record(user_id, coupon)
        qs.delete()


class CouponActivity(models.Model):
    no = models.CharField('编号', max_length=64, unique=True, db_index=True, null=True, default=get_short_no)
    title = models.CharField('活动名称', max_length=50)
    coupons = models.ManyToManyField(Coupon, verbose_name='关联消费券')
    url_link = models.CharField('领取链接', max_length=100, null=True, blank=True, editable=False, help_text='小程序加密URLLink')
    share_img = models.ImageField('分享图片', upload_to=f'{IMAGE_FIELD_PREFIX}/coupon/act',
                                  validators=[validate_image_file_extension])
    ST_ON = 1
    ST_OFF = 2
    status = models.PositiveIntegerField('活动状态', default=ST_ON, choices=[(ST_ON, '上架'), (ST_OFF, '下架')])
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '专属活动'
        ordering = ['-pk']

    def coupons_desc(self):
        return ','.join(list(self.coupons.all().values_list('name', flat=True)))

    def get_url_link(self, is_refresh=False):
        if is_refresh or not self.url_link:
            try:
                from mp.wechat_client import get_wxa_client
                wxa = get_wxa_client()
                # url = 'pages/index/index'
                url = 'pages/pagesKageB/couponActivity/couponActivity'
                data = wxa.generate_urllink(url, f'no={self.no}')
                if data['errcode'] == 0:
                    url = data['url_link']
                    self.url_link = url
                    self.save(update_fields=['url_link'])
            except Exception as e:
                log.error(e)
        return self.url_link
