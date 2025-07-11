# -*- coding: utf-8 -*-
import os
import logging
import datetime
import time
import random
import base64
import hashlib
import xmltodict
from django.conf import settings

from mall import mall_conf
from wechatpy.pay import WeChatPay
from wechatpy.pay.api import WeChatTransfer
from wechatpy.pay.utils import calculate_signature, dict_to_xml
from mall.utils import qrcode_dir, obfuscate, random_string
from rest_framework.response import Response
from common import qrutils
from restframework_ext.models import ReceiptAbstract
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, AES
from restframework_ext.exceptions import CustomAPIException

logger = logging.getLogger(__name__)


class AESCipher():
    """
    Usage:
        c = AESCipher('password').encrypt('message')
        m = AESCipher('password').decrypt(c)
    Tested under Python 3 and PyCrypto 2.6.1.
    """

    def __init__(self, key):
        self.key = hashlib.md5(key.encode('utf8')).hexdigest()

        # Padding for the input string --not
        # related to encryption itself.
        self.BLOCK_SIZE = 32  # Bytes
        self.pad = lambda s: s + (self.BLOCK_SIZE - len(s) % self.BLOCK_SIZE) * \
                             chr(self.BLOCK_SIZE - len(s) % self.BLOCK_SIZE)
        self.unpad = lambda s: s[:-ord(s[len(s) - 1:])]

    # 加密
    def encrypt(self, raw):
        raw = self.pad(raw)
        cipher = AES.new(self.key.encode('utf-8'), AES.MODE_ECB)
        return base64.b64encode(cipher.encrypt(raw))

    # 解密，针对微信用此方法即可
    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        cipher = AES.new(self.key.encode('utf-8'), AES.MODE_ECB)
        return self.unpad(cipher.decrypt(enc)).decode('utf8')


class PayClient(object):
    # inst = None
    # _client = None

    # def __new__(cls, *args, **kwargs):
    #     if cls.inst is None:
    #         cls.inst = super(cls.__class__, cls).__new__(cls)
    #     return cls.inst

    def pay(self, receipt, request):
        raise NotImplementedError

    def query_status(self, receipt):
        raise NotImplementedError


class WeChatTransferExt(WeChatTransfer):
    def transfer_to_bank(self, amount, partner_trade_no, bank_no, true_name, bank_code, desc):
        if not partner_trade_no:
            now = datetime.datetime.now()
            partner_trade_no = '{0}{1}{2}'.format(
                self.mch_id,
                now.strftime('%Y%m%d%H%M%S'),
                random.randint(1000, 10000)
            )
        data = {
            'mch_id': self.mch_id,
            'partner_trade_no': partner_trade_no,
            'nonce_str': random_string(16),
            'enc_bank_no': self._client.rsa_encrypt(str(bank_no)),
            'enc_true_name': self._client.rsa_encrypt(str(true_name)),
            'bank_code': bank_code,
            'amount': amount,
            'desc': desc
        }
        res = self._post('mmpaysptrans/pay_bank', data=data)
        logger.debug('res is {}'.format(res))
        return res


class WeChatPayExt(WeChatPay):
    transfer = WeChatTransferExt()

    def get_rsa_pem(self):
        data = dict()
        data.setdefault('mch_id', self.mch_id)
        data.setdefault('nonce_str', random_string(32))
        sign = calculate_signature(data, api_key=self.api_key)
        body = dict_to_xml(data, sign)
        body = body.encode('utf-8')
        res = self._http.request(method='post', url='https://fraud.mch.weixin.qq.com/risk/getpublickey', data=body,
                                 cert=(self.mch_cert, self.mch_key))
        res = self._handle_result(res)
        logger.debug('ras key is {}'.format(res))
        with open(mall_conf.rsa_public_key_path, 'w') as f:
            f.write(res.get('pub_key'))

    def rsa_encrypt(self, string):
        if not os.path.isfile(mall_conf.rsa_public_key_path):
            self.get_rsa_pem()
        with open(mall_conf.rsa_public_key_path)as f:
            key = RSA.importKey(f.read())
            cipher = PKCS1_OAEP.new(key)
            cipher_text = cipher.encrypt(string)
            return base64.b64encode(cipher_text)


class MpPayClient(PayClient):
    @property
    def trade_type(self):
        """
        根据支付类型返回trade_type
        :return:
        """
        return self._trade_type

    def __init__(self, config_type, wx_pay_config=None):
        """
        lp and mp payment
        :param config_type:
        """
        # super(MpPayClient, self).__init__()

        from mp.models import WeiXinPayConfig
        # https://pay.weixin.qq.com/wiki/doc/api/wxa/wxa_api.php?chapter=4_2
        if config_type in (WeiXinPayConfig.CONFIG_TYPE_LP, WeiXinPayConfig.CONFIG_TYPE_MP):
            self._trade_type = 'JSAPI'
        elif config_type == WeiXinPayConfig.CONFIG_TYPE_APP:
            self._trade_type = 'APP'
        else:
            raise CustomAPIException('不支持的付款类型')
        self.config_type = config_type
        from mp.models import WeiXinPayConfig
        if not wx_pay_config:
            self._config = WeiXinPayConfig.get_default()
        else:
            self._config = wx_pay_config
        logger.warning('pay_config,{}'.format(self._config.pay_shop_id))
        if not (self._config and self._config.is_on):
            raise CustomAPIException('微信支付未配置')
        self._client = self.create_client()

    def create_client(self):
        logger.debug('{}, {}'.format(self._config.mch_cert.path, self._config.mch_key.path))
        return WeChatPayExt(appid=self._config.app_id, api_key=self._config.pay_api_key,
                            mch_id=self._config.pay_shop_id,
                            mch_cert=self._config.mch_cert.path, mch_key=self._config.mch_key.path,
                            sub_mch_id=self._config.sub_mch_id)

    # @pysnooper.snoop(logger.debug)
    def create_order(self, receipt, trade_type='JSAPI', notify_url=None, time_expire=None):
        order_info = receipt.get_pay_order_info()
        return self._client.order.create(trade_type=trade_type, notify_url=notify_url,
                                         body=order_info.get('body'),
                                         total_fee=int(receipt.amount * 100), out_trade_no=receipt.payno,
                                         user_id=order_info.get('user_id'), attach=receipt.id, time_expire=time_expire)

    def pay(self, receipt, request):
        from mp.models import WeiXinPayConfig
        from restframework_ext.views import format_resp_data
        trade_type = request.GET.get('trade_type')
        notify_url = request.build_absolute_uri(receipt.get_notify_url())
        logger.debug('notify url is {}'.format(notify_url))
        time_expire = None
        if receipt.biz == receipt.BIZ_TICKET:
            if hasattr(receipt, 'ticket_order'):
                from ticket.models import TicketOrder
                t_order = receipt.ticket_order
                if t_order and type(t_order) == TicketOrder:
                    time_expire = t_order.get_wx_pay_end_at()
                    logger.warning('time_expire is {}'.format(time_expire))
        result = self.create_order(receipt, trade_type=trade_type if trade_type else 'JSAPI', notify_url=notify_url,
                                   time_expire=time_expire)
        if result.get('result_code') == result.get('return_code') == 'SUCCESS':
            receipt.sign = result.get('sign')
            receipt.prepay_id = result.get('prepay_id')
            receipt.save(update_fields=['sign', 'prepay_id'])
            logger.debug('create order success result is {}'.format(result))
            url = None
            if trade_type == 'NATIVE':
                code_url = result.get('code_url')
                dir, rel_url = qrcode_dir()
                if not os.path.isdir(dir):
                    os.makedirs(dir)
                qrfile_name = obfuscate(receipt.payno) + '.jpg'
                file_path = os.path.join(dir, qrfile_name)
                if not os.path.isfile(file_path):
                    qrutils.generate(code_url, size=(410, 410), save_path=file_path)
                url = request.build_absolute_uri('/'.join([rel_url, qrfile_name]))
            config = self._config
            timestamp = int(time.time())
            nonce_str = random_string(28)
            if self.config_type in (WeiXinPayConfig.CONFIG_TYPE_MP, WeiXinPayConfig.CONFIG_TYPE_LP):
                pay_sign = self._client.jsapi.get_jsapi_signature(prepay_id=result.get('prepay_id'),
                                                                  timestamp=timestamp,
                                                                  nonce_str=nonce_str)
            else:
                pay_sign = self._client.order.get_appapi_params(prepay_id=result.get('prepay_id'), timestamp=timestamp,
                                                                nonce_str=nonce_str)['sign']
            return Response(
                data=dict(prepay_id=result.get('prepay_id'),
                          timestamp=timestamp, nonce_str=nonce_str,
                          paysign=pay_sign, pay_qrcode=url, amount=receipt.amount,
                          app_id=config.app_id,
                          pay_type=receipt.pay_type,
                          pay_shop_id=config.pay_shop_id))
        else:
            return Response(status=200, data=format_resp_data(False, data=result.get('return_msg')))

    def transfer_pay(self, open_id, amount, out_trade_no, desc=u'奖励打款'):
        return self._client.transfer.transfer(user_id=open_id, amount=int(amount * 100),
                                              desc=desc, check_name='NO_CHECK', out_trade_no=out_trade_no)

    def new_refund(self, refund_payment, notify_url):
        amount = int(refund_payment.refund_amount * 100)
        total_fee = int(refund_payment.order.actual_amount * 100)
        return self._client.refund.apply(total_fee=total_fee, refund_fee=amount,
                                         out_refund_no=refund_payment.out_refund_no,
                                         transaction_id=refund_payment.transaction_id, notify_url=notify_url)

    def refund(self, refund_payment, request):
        amount = int(refund_payment.amount * 100)
        url = request.build_absolute_uri(mall_conf.refund_notify_url)
        return self._client.refund.apply(total_fee=amount, refund_fee=amount,
                                         out_refund_no=refund_payment.pay_no,
                                         transaction_id=refund_payment.stransaction_id, notify_url=url)

    def ticket_refund(self, ticket_refund, refund_notify_url):
        amount = int((ticket_refund.refund_amount - ticket_refund.theater_amount) * 100)
        total_fee = int(ticket_refund.order.receipt.amount * 100)
        # url = '{}/api/show/order/refund_notify/'.format(config['template_url'])
        return self._client.refund.apply(total_fee=total_fee, refund_fee=amount,
                                         out_refund_no=ticket_refund.out_refund_no,
                                         transaction_id=ticket_refund.transaction_id, notify_url=refund_notify_url)

    def parse_pay_result(self, xml):
        return self._client.parse_payment_result(xml)

    def query_status(self, receipt):
        result = self._client.order.query(receipt.transaction_id, receipt.payno)
        if result.get('trade_state') == 'SUCCESS':
            receipt.set_paid(transaction_id=result.get('transaction_id'))
            return True

    def check_signature(self, params):
        return self._client.check_signature(params)

    def transfer_to_bank(self, amount, bank_no, true_name, bank_code, desc, partner_trade_no):
        return self._client.transfer.transfer_to_bank(amount=int(amount * 100), bank_no=bank_no, true_name=true_name,
                                                      bank_code=bank_code, desc=desc, partner_trade_no=partner_trade_no)

    def parse_refund_result(self, xml):
        data = xmltodict.parse(xml).get('xml')
        # logger.debug('parse_refund_result,{}'.format(data))
        # logger.debug('api_key,{}'.format(self._client.api_key))
        aes_obj = AESCipher(self._client.api_key)
        return xmltodict.parse(aes_obj.decrypt(data.get('req_info').encode('utf-8'))).get('root')


mp_pay_client = dict()
app_pay_client = None
lp_pay_client = dict()


class WxAppPayClient(MpPayClient):

    def __init__(self):
        # super(WxAppPayClient, self).__init__(config_type)
        super(WxAppPayClient, self).__init__(ReceiptAbstract.get_config_type(ReceiptAbstract.PAY_WeiXin_APP))


# @pysnooper.snoop(logger.debug)
def get_mp_pay_client(pay_type=None, wx_pay_config=None):
    """
    :param pay_type: required
    :param config_type:depracted
    :return:
    """
    from restframework_ext.models import ReceiptAbstract
    from mp.models import WeiXinPayConfig
    if pay_type not in (ReceiptAbstract.PAY_WeiXin_LP, ReceiptAbstract.PAY_WeiXin_MP, ReceiptAbstract.PAY_WeiXin_APP):
        raise CustomAPIException('参数错误, 必填pay_type')
    config_type = ReceiptAbstract.get_config_type(pay_type)
    key = str(wx_pay_config.id) if wx_pay_config else ''
    if config_type == WeiXinPayConfig.CONFIG_TYPE_MP:
        global mp_pay_client
        if not mp_pay_client.get(key):
            mp_pay_client[key] = MpPayClient(config_type, wx_pay_config)
        return mp_pay_client[key]
    elif config_type == WeiXinPayConfig.CONFIG_TYPE_LP:
        global lp_pay_client
        if not lp_pay_client.get(key):
            # lp_pay_client = check_and_get_efps() or MpPayClient(config_type)
            lp_pay_client[key] = MpPayClient(config_type, wx_pay_config)
        return lp_pay_client[key]
    elif config_type == WeiXinPayConfig.CONFIG_TYPE_APP:
        global app_pay_client
        if not app_pay_client:
            app_pay_client = WxAppPayClient()
        return app_pay_client
    else:
        logger.error("unknown config_type: %s" % config_type)
        raise CustomAPIException('支付类型错误')


def get_default_pay_client():
    """
    返回默认的client, 如果是仅小程序，则返回小程序; 公众号则返回公众号等;
    影响的是付款 、通知、退款，以及微信付款到零钱和银行卡，这些地方用的是默认.
    :return:
    """
    return get_mp_pay_client(ReceiptAbstract.PAY_WeiXin_LP)


def get_default_pay_type():
    from common.config import get_config
    return get_config()['pay']['default_pay_type']


def get_wechat_pay_notice_client():
    """
    返回默认的client, 如果是仅小程序，则返回小程序; 公众号则返回公众号等;
    影响的是付款 、通知、退款，以及微信付款到零钱和银行卡，这些地方用的是默认.
    :return:
    """
    return get_mp_pay_client(get_default_pay_type())
