# coding=utf-8
from django.core.validators import validate_image_file_extension
from django.db import models

from common.config import IMAGE_FIELD_PREFIX
from mp.models import WeiXinPayConfig
from restframework_ext.models import UseNoAbstract, ReceiptAbstract
from django.utils import timezone
from random import sample
from django.conf import settings
import simplejson as json
import logging
from django.core.exceptions import ValidationError
from restframework_ext.exceptions import CustomAPIException
from django.db import close_old_connections

SR_COUPON = 1
SR_TICKET = 2
SR_CODE = 3
SR_GOOD = 4
PRIZE_SOURCE_TYPE_CHOICES = ((SR_COUPON, '消费券'), (SR_TICKET, '纸质票'), (SR_CODE, '券码'), (SR_GOOD, '实物奖品'))
notify_url = '/api/blind/receipt/notify/'
refund_notify_url = '/api/blind/receipt/refund_notify/'
log = logging.getLogger(__name__)


def cancel_minutes_limit(value):
    if value < 5:
        raise ValidationError("必须大于等于5分钟")
    else:
        return value


def price_his_no(tail_length=3):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return '%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def blind_refund_no(tail_length=3):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'BR%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


class BlindBasic(models.Model):
    auto_cancel_minutes = models.PositiveSmallIntegerField('自动关闭订单分钟数', default=5,
                                                           help_text='订单创建时间开始多少分钟后未支付自动取消订单',
                                                           validators=[cancel_minutes_limit], editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '盲盒配置'

    @classmethod
    def get(cls):
        return cls.objects.first()


class Prize(UseNoAbstract):
    title = models.CharField('名称', max_length=128)
    STATUS_OFF = 2
    STATUS_ON = 1
    STATUS_CHOICES = ((STATUS_OFF, U'下架'), (STATUS_ON, U'上架'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_ON, help_text='下架后则不会被抽中')
    source_type = models.PositiveSmallIntegerField('奖品类型', choices=PRIZE_SOURCE_TYPE_CHOICES, default=SR_COUPON)
    RA_COMMON = 1
    RA_RARE = 2
    RA_HIDDEN = 3
    RARE_TYPE_CHOICES = ((RA_COMMON, '普通款'), (RA_RARE, '稀有款'), (RA_HIDDEN, '隐藏款'))
    rare_type = models.PositiveSmallIntegerField('稀有类型', choices=RARE_TYPE_CHOICES, default=RA_COMMON)
    amount = models.DecimalField('价值', max_digits=13, decimal_places=2, default=0)
    desc = models.TextField('描述', max_length=1000)
    instruction = models.TextField('兑奖说明')
    stock = models.IntegerField('库存数量', default=0)
    weight = models.PositiveSmallIntegerField('权重数', default=0)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '奖品'
        ordering = ['-pk']

    @classmethod
    def prize_update_stock_from_redis(cls):
        close_old_connections()
        from blind_box.stock_updater import prsc
        prsc.persist()

    def prize_change_stock(self, mul):
        ret = True
        prize_upd = []
        prize_upd.append((self.pk, mul, 0))
        from blind_box.stock_updater import prsc
        succ1, tfc_result = prsc.batch_incr(prize_upd)
        if succ1:
            prsc.batch_record_update_ts(prsc.resolve_ids(tfc_result))
        else:
            log.warning(f"prize incr failed,{self.pk}")
            # 库存不足
            ret = False
        return ret

    def prize_redis_stock(self, stock=None):
        # 初始化库存
        from blind_box.stock_updater import prsc, StockModel
        if stock == None:
            stock = self.stock
        prsc.append_cache(StockModel(_id=self.id, stock=stock))

    def prize_del_redis_stock(self):
        from blind_box.stock_updater import prsc
        prsc.remove(self.id)


class BlindBox(UseNoAbstract):
    title = models.CharField('名称', max_length=128)
    STATUS_OFF = 2
    STATUS_ON = 1
    STATUS_CHOICES = ((STATUS_OFF, '下架'), (STATUS_ON, '上架'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_ON, help_text='下架后则不会被抽中')
    GR_THREE = 3
    GR_SIX = 6
    GR_NINE = 9
    GR_CHOICES = ((GR_THREE, '3格'), (GR_SIX, '6格'), (GR_NINE, '9格'))
    grids_num = models.PositiveSmallIntegerField(u'格子数量', choices=GR_CHOICES, default=GR_THREE)
    price = models.DecimalField('价格', max_digits=13, decimal_places=2, default=0)
    logo = models.ImageField('盲盒图片', upload_to=f'{IMAGE_FIELD_PREFIX}/blind/box',
                             validators=[validate_image_file_extension])
    desc = models.TextField('描述', max_length=1000)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '盲盒'
        ordering = ['-pk']


class BlindReceipt(ReceiptAbstract):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'用户', null=True, on_delete=models.SET_NULL)
    BIZ_BLIND = 1
    BIZ_CHOICES = [(BIZ_BLIND, '盲盒订单')]
    biz = models.SmallIntegerField('业务类型', default=BIZ_BLIND, choices=BIZ_CHOICES)
    attachment = models.TextField('附加数据', null=True, blank=True, help_text='请勿修改此字段')
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-pk']
        verbose_name = verbose_name_plural = '盲盒支付记录'

    def __str__(self):
        return f"{str(self.user)} - {self.amount}元"

    @classmethod
    def create_record(cls, amount, user, pay_type, biz, wx_pay_config=None):
        return cls.objects.create(amount=amount, user=user, pay_type=pay_type, biz=biz, wx_pay_config=wx_pay_config)

    def get_pay_order_info(self):
        return notify_url

    @property
    def paid(self):
        return self.status == self.STATUS_FINISHED

    def get_notify_url(self):
        return dict(body='消费卷支付记录订单', user_id=self.get_user_id())

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
        if self.biz == self.BIZ_BLIND:
            self.blind_receipt.set_paid()
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


class PrizeOrder(models.Model):
    ST_DEFAULT = 1
    ST_PAID = 2
    ST_CANCEL = 3
    ST_REFUNDING = 4
    ST_REFUNDED = 5
    PAYMENT_STATUS = (
        (ST_DEFAULT, '未付款'),
        (ST_PAID, '已支付'),
        (ST_CANCEL, '已取消'),
        (ST_REFUNDING, '退款中'),
        (ST_REFUNDED, '已退款'),
    )
    order_no = models.CharField('订单号', max_length=128, unique=True, default=price_his_no, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, verbose_name='用户', null=True)
    blind_box = models.ForeignKey(BlindBox, on_delete=models.SET_NULL, verbose_name='盲盒', null=True)
    mobile = models.CharField('手机号', max_length=20)
    status = models.PositiveSmallIntegerField('状态', choices=PAYMENT_STATUS, default=ST_DEFAULT)
    amount = models.DecimalField('实付金额', max_digits=10, decimal_places=2)
    refund_amount = models.DecimalField('已退款金额', max_digits=10, decimal_places=2, default=0)
    receipt = models.OneToOneField(BlindReceipt, verbose_name='支付记录', on_delete=models.CASCADE,
                                   related_name='blind_receipt')
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    pay_at = models.DateTimeField('支付时间', null=True, blank=True)
    transaction_id = models.CharField('交易号', max_length=100, null=True, blank=True)
    snapshot = models.TextField('盲盒快照', help_text='下单时保存的快照', editable=False)

    class Meta:
        verbose_name = verbose_name_plural = '盲盒订单'
        ordering = ['-pk']

    def __str__(self):
        return self.order_no

    @classmethod
    def can_refund_status(cls):
        return [cls.ST_PAID]

    def push_refund(self, amount):
        self.refund_amount += amount
        self.status = self.ST_REFUNDING
        self.save(update_fields=['refund_amount', 'status'])

    def set_refunded(self):
        self.refund_at = timezone.now()
        self.status = self.ST_REFUNDED
        self.save(update_fields=['status', 'refund_at'])
        # 退款成功后返还库存
        self.return_prize_stock()

    def set_paid(self):
        if self.status in [self.ST_DEFAULT, self.ST_CANCEL]:
            self.status = self.ST_PAID
            self.pay_at = timezone.now()
            self.save(update_fields=['status', 'pay_at'])

    @classmethod
    def get_snapshot(cls, blind_box: BlindBox):
        from blind_box.serializers import BlindBoxSnapshotSerializer
        data = BlindBoxSnapshotSerializer(blind_box).data
        return json.dumps(data)

    def send_prize(self):
        qs = Prize.objects.filter(status=Prize.STATUS_ON, stock__gt=0)

    def set_cancel(self):
        if self.status == self.ST_DEFAULT:
            receipt = self.receipt
            if receipt.pay_type == receipt.PAY_WeiXin_LP:
                receipt.query_status(self.order_no)
            if receipt.paid:
                receipt.biz_paid()
                return False, '取消失败订单已付款'
            self.status = self.ST_CANCEL
            self.cancel_at = timezone.now()
            self.save(update_fields=['status', 'cancel_at'])
            # 归还库存
            self.return_prize_stock()
        return True, ''

    def return_prize_stock(self):
        # 归还库存
        for item in self.prize_items.all():
            prize = item.prize
            prize.prize_change_stock(1)


class PrizeOrderItem(models.Model):
    order = models.ForeignKey(PrizeOrder, on_delete=models.CASCADE, verbose_name='盲盒订单', related_name='prize_items')
    prize = models.ForeignKey(Prize, on_delete=models.SET_NULL, verbose_name='奖品', null=True)
    amount = models.DecimalField('价值', max_digits=13, decimal_places=2, default=0)
    source_type = models.PositiveSmallIntegerField('奖品类型', choices=PRIZE_SOURCE_TYPE_CHOICES, default=SR_COUPON)
    snapshot = models.TextField('奖品快照', help_text='中奖时保存的快照', editable=False)

    class Meta:
        verbose_name = verbose_name_plural = '奖品明细'
        ordering = ['-pk']

    def __str__(self):
        return '奖品明细'

    @classmethod
    def get_snapshot(cls, prize: Prize):
        from blind_box.serializers import PrizeSnapshotSerializer
        data = PrizeSnapshotSerializer(prize).data
        return json.dumps(data)
