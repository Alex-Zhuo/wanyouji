# coding: utf-8
from django.db import models
from django.conf import settings

from common.utils import get_no, get_short_no
from mall.utils import randomstrwithdatetime
from mall.mall_conf import default_pay_type
import logging

log = logging.getLogger(__name__)


class DateDetailAbstract(models.Model):
    create_at = models.DateTimeField(u'创建时间', auto_now_add=True)
    update_at = models.DateTimeField(u'更新时间', auto_now=True)

    class Meta:
        abstract = True


class UseNoAbstract(models.Model):
    no = models.CharField('编号', max_length=64, unique=True, db_index=True, null=True, default=get_no)

    class Meta:
        abstract = True


class UseShortNoAbstract(models.Model):
    no = models.CharField('编号', max_length=64, unique=True, db_index=True, null=True, default=get_short_no,
                          editable=False)

    class Meta:
        abstract = True


class ReceiptAbstract(DateDetailAbstract):
    payno = models.CharField(u'商户订单号', max_length=100, default=randomstrwithdatetime, db_index=True)
    amount = models.DecimalField(u'实付金额', max_digits=13, decimal_places=2, default=0.0)
    STATUS_FINISHED = 1
    STATUS_PROCCESSING = 0
    STATUS_CHOICES = ((STATUS_PROCCESSING, u'未付款'), (STATUS_FINISHED, '已付款'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_PROCCESSING)
    PAY_NOT_SET = -1
    PT_OFFLINE = 0
    PAY_WeiXin_MP = 1
    PAY_UMF_MP = 2
    PAY_UMF_H5 = 3
    PAY_COMMISSION_BALANCE = 4
    PAY_WeiXin_APP = 6
    PAY_WeiXin_LP = 7
    PAY_TikTok_LP = 8
    PAY_CARD_JC = 9
    PAY_KS = 10
    PAY_XHS = 11
    PAY_CHOICES = (
        (PAY_NOT_SET, '空'), (PAY_WeiXin_LP, '微信小程序支付'))
    pay_type = models.SmallIntegerField('付款类型', choices=PAY_CHOICES, default=PAY_NOT_SET)
    sign = models.CharField('微信支付签名', max_length=32, null=True, blank=True)
    transaction_id = models.CharField('微信支付单号', max_length=32, null=True, blank=True)
    prepay_id = models.CharField('微信支付预支付订单号', max_length=100, null=True, blank=True)

    def __unicode__(self):
        return u'单号: {}, 金额: {}, 支付方式: {}'.format(self.payno, self.amount, self.get_pay_type_display())

    class Meta:
        abstract = True
        verbose_name = verbose_name_plural = u'收款记录'

    @classmethod
    def get_config_type(cls, pay_type):
        from mp.models import WeiXinPayConfig
        if pay_type == cls.PAY_WeiXin_MP:
            return WeiXinPayConfig.CONFIG_TYPE_MP
        elif pay_type == cls.PAY_WeiXin_LP:
            return WeiXinPayConfig.CONFIG_TYPE_LP
        elif pay_type == cls.PAY_WeiXin_APP:
            return WeiXinPayConfig.CONFIG_TYPE_APP
        raise ValueError('未知的支付类型:%s' % pay_type)

    def get_pay_order_info(self):
        raise NotImplementedError()

    @property
    def paid(self):
        raise NotImplementedError()

    def set_pay_type(self, pay_type=None):
        if self.pay_type != self.PAY_NOT_SET:
            return
        self.pay_type = pay_type if pay_type else default_pay_type
        self.save(update_fields=['pay_type'])

    @classmethod
    def umf_pay_type(cls):
        return [cls.PAY_UMF_MP, cls.PAY_UMF_H5]

    @classmethod
    def weixin_pay_type(cls):
        return [cls.PAY_WeiXin_MP]

    def get_notify_url(self):
        raise NotImplementedError()

    # @pysnooper.snoop(logger.debug)
    def query_status(self, order_no=None):
        try:
            if self.pay_type == self.PAY_TikTok_LP:
                from douyin import get_dou_yin
                mp_pay_client = get_dou_yin()
                st, channel_pay_id = mp_pay_client.query_status(order_no)
                if st:
                    self.set_paid(transaction_id=channel_pay_id)
            elif self.pay_type == self.PAY_KS:
                from kuaishou_wxa.api import get_ks_wxa
                mp_pay_client = get_ks_wxa()
                st, data = mp_pay_client.query_status(order_no)
                if st:
                    self.set_paid(transaction_id=data['ks_order_no'])
            elif self.pay_type == self.PAY_XHS:
                from xiaohongshu.models import XhsOrder
                xhs_order = XhsOrder.get_order(order_no)
                st, transaction_id = xhs_order.query_status()
                if st:
                    self.set_paid(transaction_id=transaction_id)
            else:
                from mall.pay_service import get_mp_pay_client
                mp_pay_client = get_mp_pay_client(self.pay_type, self.wx_pay_config)
                if self.prepay_id:
                    mp_pay_client.query_status(self)
        except Exception as e:
            log.error(e)

    def update_info(self):
        raise NotImplementedError()
