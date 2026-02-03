from django.core.validators import validate_image_file_extension
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid
from django.core.exceptions import ValidationError
from django.conf import settings
from caches import get_redis_name, RedisCounter, run_with_lock, get_redis
from common.config import IMAGE_FIELD_PREFIX
from mp.models import WeiXinPayConfig
from restframework_ext.models import ReceiptAbstract, UseNoAbstract
import logging
from restframework_ext.exceptions import CustomAPIException
from random import sample
from django.db.transaction import atomic

log = logging.getLogger(__name__)
notify_url = '/api/act_receipts/notify/'
refund_notify_url = '/api/act_receipts/refund_notify/'


def act_cancel_minutes_limit(value):
    if value < 5:
        raise ValidationError("必须大于等于5分钟")
    else:
        return value


def act_order_no(tail_length=3):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'GO%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def act_refund_no(tail_length=3):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'GR%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


class ActivityConfig(models.Model):
    auto_cancel_minutes = models.PositiveSmallIntegerField('自动关闭订单分钟数', default=5,
                                                           help_text='订单创建时间开始多少分钟后未支付自动取消订单，解锁位置',
                                                           validators=[act_cancel_minutes_limit])

    class Meta:
        verbose_name_plural = verbose_name = '基本配置'

    @classmethod
    def get(cls):
        return cls.objects.first()


class ActivityCategory(models.Model):
    name = models.CharField('分类名称', max_length=50, unique=True)
    is_active = models.BooleanField('是否启用', default=True)
    post_total = models.PositiveIntegerField('累计活动数量', default=0)

    class Meta:
        verbose_name_plural = verbose_name = '兴趣分类'

    def __str__(self):
        return self.name

    @classmethod
    def update_post_total(cls, cate_id: int):
        pass


class GroupActivity(UseNoAbstract):
    ST_DEFAULT = 1
    ST_CLOSE = 2
    ST_FINISH = 3
    ACTIVITY_STATUS = (
        (1, '已发布'),
        (2, '已关闭'),
        (3, '已成团'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(ActivityCategory, on_delete=models.SET_NULL, null=True, verbose_name='活动分类')
    title = models.CharField('活动标题', max_length=100)
    description = models.TextField('活动描述')
    required_members = models.PositiveIntegerField('成团人数')
    current_members = models.PositiveIntegerField('当前人数', default=0)
    contact_phone = models.CharField('联系电话', max_length=20)
    latitude = models.DecimalField('纬度', max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField('经度', max_digits=9, decimal_places=6, null=True, blank=True)
    address = models.CharField('详细地址', max_length=200)
    registration_deadline = models.DateTimeField('报名截止时间')
    status = models.PositiveSmallIntegerField('状态', choices=ACTIVITY_STATUS, default=ST_DEFAULT)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name_plural = verbose_name = '拼团活动'
        ordering = ['-pk']

    def __str__(self):
        return self.title

    def is_registration_open(self):
        return self.status == self.ST_DEFAULT and timezone.now() < self.registration_deadline

    def time_remaining(self):
        return self.registration_deadline - timezone.now()

    @property
    def is_joinable(self):
        return self.is_registration_open and self.current_members < self.required_members

    def check_can_payment(self):
        """
        使用Redis实现并发安全的支付处理
        """
        redis_client = get_redis()
        activity = self
        # 使用Redis计数器检查人数
        counter_key = get_redis_name(f"act_counter:{activity.id}")
        current_count = RedisCounter.increment(counter_key, activity.required_members)
        if current_count is None:
            raise CustomAPIException('活动人数已满')
        # 使用分布式锁保护数据库更新
        lock_key = get_redis_name(f"act_pay:{activity.id}")
        with run_with_lock(lock_key, 10) as acquired:
            if not acquired:
                raise CustomAPIException('系统繁忙，请稍后再试')
            # 再次检查活动状态(双重检查)
            activity.refresh_from_db()
            if not activity.is_joinable:
                # 回滚Redis计数器
                redis_client.decr(counter_key)
                raise CustomAPIException('该活动已截止或人数已满')

    def check_can_join(self, user) -> dict:
        st = True
        msg = None
        code = 0
        if not self.is_joinable:
            st = False
            msg = '该活动已截止或人数已满'
            code = 10001
            # 检查是否已经参与
        existing_participant = ActivityParticipant.objects.filter(activity=self, user=user).first()
        if existing_participant:
            st = False
            if existing_participant.status == ActivityParticipant.ST_PAID:
                msg = '您已经成功参与该活动'
                code = 10002
            else:
                msg = '您已报名但未支付'
        return dict(msg=msg, st=st, code=code)


class ActivityImage(models.Model):
    activity = models.ForeignKey(GroupActivity, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField('活动图片', upload_to=f'{IMAGE_FIELD_PREFIX}/activity_images/',validators=[validate_image_file_extension])
    order = models.PositiveIntegerField('排序', default=0, help_text='从小到大排')

    class Meta:
        verbose_name_plural = verbose_name = '活动图片'
        ordering = ['order']

    def __str__(self):
        return f"{self.activity.title} 的图片"


class ActivityReceipt(ReceiptAbstract):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'用户', related_name='act_receipts', null=True,
                             on_delete=models.SET_NULL)
    BIZ_ACT = 1
    BIZ_CHOICES = [(BIZ_ACT, '活动订单')]
    biz = models.SmallIntegerField('业务类型', default=BIZ_ACT, choices=BIZ_CHOICES)
    attachment = models.TextField('附加数据', null=True, blank=True, help_text='请勿修改此字段')
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-pk']
        verbose_name = verbose_name_plural = '活动支付记录'

    def __str__(self):
        return f"{str(self.user)} - {self.amount}元"

    @classmethod
    def create_record(cls, amount, user, pay_type, wx_pay_config=None):
        return cls.objects.create(amount=amount, user=user, pay_type=pay_type, wx_pay_config=wx_pay_config)

    def get_pay_order_info(self):
        return notify_url

    @property
    def paid(self):
        return self.status == self.STATUS_FINISHED

    def get_notify_url(self):
        return dict(body='拼团活动订单', user_id=self.get_user_id())

    def get_user_id(self):
        if self.pay_type == self.PAY_WeiXin_LP:
            return self.user.lp_openid
        else:
            log.error('unsupported pay_type: %s' % self.pay_type)
            raise CustomAPIException('不支持的支付类型')

    def update_info(self):
        from mall.pay_service import get_mp_pay_client
        from wechatpy import WeChatPayException
        c = get_mp_pay_client(self.pay_type, self.wx_pay_config)
        try:
            res = c.query_order(self)
            if res:
                self.transaction_id = res.get('transaction_id')
                self.save(update_fields=['transaction_id'])
        except WeChatPayException as e:
            log.error(e)

    @classmethod
    def available_pay_types(self):
        return [self.PAY_WeiXin_LP]

    def biz_paid(self):
        """
        付款成功时,根据业务类型决定处理方法
        :return:
        """
        if self.biz == self.BIZ_ACT:
            self.act_receipt.set_paid()
        else:
            log.fatal('unkonw biz: %s, of receipt: %s' % (self.biz, self.pk))

    def set_paid(self, pay_type=ReceiptAbstract.PAY_WeiXin_LP, transaction_id=None):
        if self.paid:
            return
        self.status = self.STATUS_FINISHED
        self.pay_type = pay_type
        self.transaction_id = transaction_id if transaction_id else self.transaction_id
        self.save(update_fields=['status', 'transaction_id'])
        self.biz_paid()


class ActivityParticipant(models.Model):
    ST_PENDING = 1
    ST_PAID = 2
    ST_REFUNDING = 3
    ST_REFUNDED = 4
    PAYMENT_STATUS = (
        (ST_PENDING, '待支付'),
        (ST_PAID, '已支付'),
        (ST_REFUNDING, '退款中'),
        (ST_REFUNDED, '已退款'),
    )
    order_no = models.CharField(u'订单号', max_length=128, unique=True, default=act_order_no, db_index=True)
    activity = models.ForeignKey(GroupActivity, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='joined_activities')
    joined_at = models.DateTimeField('加入时间', auto_now_add=True)
    status = models.PositiveSmallIntegerField('支付状态', choices=PAYMENT_STATUS, default=ST_PENDING)
    amount = models.DecimalField('支付金额', max_digits=10, decimal_places=2)
    refund_amount = models.DecimalField('已退款金额', max_digits=10, decimal_places=2, default=0)
    pay_at = models.DateTimeField('支付时间', null=True, blank=True)
    transaction_id = models.CharField('交易号', max_length=100, null=True, blank=True)
    receipt = models.OneToOneField(ActivityReceipt, verbose_name='支付记录', on_delete=models.CASCADE,
                                   related_name='act_receipt')

    class Meta:
        verbose_name = verbose_name_plural = '活动参与订单'
        unique_together = ('activity', 'user')

    def __str__(self):
        return f"{str(self.user)} 参加了 {self.activity.title}"

    def push_refund(self, amount):
        self.refund_amount += amount
        self.status = self.ST_REFUNDING
        self.save(update_fields=['refund_amount', 'status'])

    def set_refunded(self):
        self.refund_at = timezone.now()
        self.status = self.ST_REFUNDED
        self.save(update_fields=['status', 'refund_at'])

    def set_paid(self):
        # 更新活动的当前有效人数（只计算已支付的）
        if self.status == 'paid':
            paid_participants = ActivityParticipant.objects.filter(
                activity=self.activity,
                payment_status='paid'
            ).count()
            self.activity.current_members = paid_participants
            self.activity.save()

            # 检查是否成团
            if paid_participants >= self.activity.required_members:
                self.activity.status = 'completed'
                self.activity.save()


class CommonRefundAbstract(models.Model):
    STATUS_DEFAULT = 1
    STATUS_PAYING = 2
    STATUS_PAY_FAILED = 3
    STATUS_FINISHED = 4
    STATUS_CANCELED = 5
    STATUS_CHOICES = (
        (STATUS_DEFAULT, '待退款'), (STATUS_PAYING, '退款支付中'), (STATUS_PAY_FAILED, '退款支付失败'), (STATUS_FINISHED, '已完成'),
        (STATUS_CANCELED, '已拒绝'))
    status = models.IntegerField('状态', choices=STATUS_CHOICES, default=STATUS_DEFAULT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE)
    refund_amount = models.DecimalField(u'退款金额', max_digits=13, decimal_places=2, default=0)
    refund_reason = models.CharField('退款原因', max_length=200, null=True, blank=True)
    amount = models.DecimalField(u'实退金额', max_digits=13, decimal_places=2, default=0)
    error_msg = models.CharField('退款返回信息', max_length=1000, null=True, blank=True)
    transaction_id = models.CharField('交易号', max_length=100, null=True, blank=True)
    refund_id = models.CharField('退款方退款单号', max_length=32, null=True, blank=True)
    return_code = models.CharField('微信通信结果', max_length=20, null=True, blank=True)
    result_code = models.CharField('微信返回结果', max_length=20, null=True, blank=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    confirm_at = models.DateTimeField('确认时间', null=True, blank=True)
    finish_at = models.DateTimeField('完成时间', null=True, blank=True)
    op_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='操作退款用户', on_delete=models.CASCADE, null=True,
                                blank=True, related_name='+')

    class Meta:
        abstract = True

    def wx_refund(self, *args):
        raise NotImplementedError()

    def get_refund_notify_url(self):
        return refund_notify_url

    @classmethod
    def create_record(cls, order, amount=0, refund_reason=None):
        receipt = order.receipt
        refund_amount = amount if amount > 0 else order.amount
        if receipt.status == ActivityReceipt.STATUS_FINISHED and receipt.transaction_id:
            inst = cls.objects.create(user=order.user, order=order, refund_amount=refund_amount,
                                      order_no=order.order_no,
                                      refund_reason=refund_reason, transaction_id=receipt.transaction_id)
            order.push_refund(refund_amount)
            return True, '', inst
        else:
            return False, '该订单未付款不能退款', None

    @atomic
    def set_confirm(self, op_user=None):
        try:
            st = self.wx_refund()
            msg = self.error_msg
            if st:
                self.status = self.STATUS_PAYING
                self.confirm_at = timezone.now()
                self.op_user = op_user
                self.save(update_fields=['status', 'confirm_at', 'op_user'])
            return st, msg
        except Exception as e:
            log.error(e)
            raise CustomAPIException('退款失败，联系管理员')


class GroupParticipantRefund(CommonRefundAbstract):
    order = models.ForeignKey(ActivityParticipant, related_name='act_part_refund', verbose_name='退款订单',
                              on_delete=models.CASCADE)
    order_no = models.CharField(u'订单号', max_length=128)
    out_refund_no = models.CharField(u'退款单号', max_length=64, default=act_refund_no, unique=True, db_index=True)

    class Meta:
        verbose_name_plural = verbose_name = '活动退款记录'
        ordering = ['-pk']

    @classmethod
    def user_refund(cls, order, op_user=None, reason=None):
        st, msg, inst = cls.create_record(order, reason)
        if st:
            st, msg = inst.set_confirm(op_user)
        if not st:
            raise CustomAPIException(msg)

    def wx_refund(self, request):
        receipt = self.order.receipt
        if not receipt.transaction_id:
            receipt.update_info()
        from mall.pay_service import get_mp_pay_client
        mp_pay_client = get_mp_pay_client(receipt.pay_type, receipt.wx_pay_config)
        refund_notify_url = request.build_absolute_uri(self.get_refund_notify_url())
        result = mp_pay_client.new_refund(self, notify_url=refund_notify_url)
        self.return_code = result.get('return_code')
        self.result_code = result.get('result_code')
        self.error_msg = '{}, {}'.format(result.get('return_msg'), result.get('err_code_des'))
        self.refund_id = result.get('refund_id', None)
        self.save(update_fields=['return_code', 'result_code', 'error_msg', 'refund_id'])
        if self.return_code == self.result_code == 'SUCCESS':
            return True
        return False

    def set_cancel(self, op_user):
        self.status = self.STATUS_CANCELED
        self.confirm_at = timezone.now()
        self.op_user = op_user
        self.save(update_fields=['status', 'confirm_at', 'op_user'])
        self.return_order_status()

    def return_order_status(self):
        if self.order.refund_amount > 0:
            self.order.status = self.order.ST_PAID
            self.order.refund_amount -= self.refund_amount
            self.order.save(update_fields=['status', 'refund_amount'])

    def set_fail(self, msg=None):
        self.status = self.STATUS_PAY_FAILED
        self.finish_at = timezone.now()
        self.error_msg = msg
        self.save(update_fields=['status', 'error_msg', 'finish_at'])
        self.return_order_status()

    def set_finished(self, amount):
        """
        设置为完成:
        1.在退款支付通知回调中
        2.后台手动
        :return:
        """
        from decimal import Decimal
        self.status = self.STATUS_FINISHED
        self.finish_at = timezone.now()
        self.amount = Decimal(amount) / 100
        self.save(update_fields=['status', 'finish_at', 'amount'])
        self.order.set_refunded()
