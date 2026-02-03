# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import requests
from optionaldict import optionaldict
from Crypto.Cipher import AES
from common.config import get_config
import logging
from kuaishou_wxa.exceptions import KShouClientException, APILimitedException
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Cryptodome.Hash import MD5, SHA256
import base64
import warnings
import uuid
import json
from caches import with_redis
import os
from django.utils import timezone
import string
from random import sample
from datetime import datetime
import hashlib
from common.utils import get_config, ascii_order_dict, get_jwt
from rest_framework.exceptions import ValidationError
from hashlib import md5
import time

logger = logging.getLogger(__name__)
from common.utils import get_timestamp


def random_string(length=16):
    rule = string.ascii_letters + string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


class KShouWxaAbstract(object):
    API_BASE_URL = 'https://open.kuaishou.com/'

    def _request(self, method, url_or_endpoint, params=None, headers=None, **kwargs):
        uri = self.API_BASE_URL
        if not url_or_endpoint.startswith(('http://', 'https://')):
            url = '{base}{endpoint}'.format(
                base=uri,
                endpoint=url_or_endpoint
            )
        else:
            url = url_or_endpoint
        if isinstance(kwargs.get('data', ''), dict):
            body = json.dumps(kwargs['data'], ensure_ascii=False)
            body = body.encode('utf-8')
            kwargs['data'] = body
        if method == 'post':
            res = requests.post(url, json=params, headers=headers)
        else:
            res = requests.get(url, params=params, headers=headers)
        try:
            res.raise_for_status()
        except requests.RequestException as reqe:
            raise KShouClientException(
                errcode=None,
                errmsg=None,
                client=self,
                request=reqe.request,
                response=reqe.response)
        ret_data = json.loads(res.content.decode('utf-8', 'ignore'), strict=False)
        logger.error(ret_data)
        if ret_data.get('result'):
            result = ret_data.get('result')
            if result not in [1, '1']:
                # logger.error(result)
                raise APILimitedException(
                    errcode=result,
                    errmsg=ret_data['error_msg'],
                    client=self,
                    request=res.request,
                    response=res)
        return ret_data

    def _get(self, url, params=None, headers=None, **kwargs):
        return self._request(
            method='get',
            url_or_endpoint=url,
            params=params,
            headers=headers,
            **kwargs
        )

    def _post(self, url, params=None, headers=None, **kwargs):
        return self._request(
            method='post',
            url_or_endpoint=url,
            params=params,
            headers=headers,
            **kwargs
        )


class KShouWxa(KShouWxaAbstract):
    # 快手授权第三方小程序
    def __init__(self):
        from kuaishou_wxa.models import KShouWxa, KShouPlatform
        # config = get_config()
        # ks_config = config['ks_third']
        ks_config = KShouPlatform.get()
        self.component_app_id = ks_config.component_app_id
        self.component_token = ks_config.component_token
        self.component_app_secret = ks_config.component_app_secret
        self.component_key = ks_config.component_key
        self.ks_third_url = ks_config.api_url
        ks_wxa = KShouWxa.get()
        self.app_id = ks_wxa.app_id
        self.app_secret = ks_wxa.app_secret
        component_access_token_key = 'cpt_token_{}'.format(self.app_id)
        self.component_access_token_key = self.get_redis_key(component_access_token_key)
        authorizer_access_token_key = 'auth_token_{}'.format(self.app_id)
        self.authorizer_access_token_key = self.get_redis_key(authorizer_access_token_key)

    def get_redis_key(self, key):
        config = get_config()
        prefix = config['redis']['prefix']
        return '{}_{}'.format(prefix, key)

    def check_sign(self, http_body: bytes, sign: str):
        """
        参考例子
        https://mp.kuaishou.com/docs/saas/develop/api/encryptedMsg.html
        """
        unsign_str = http_body + self.component_token.encode()
        sha = hashlib.sha1()
        sha.update(unsign_str)
        c_sign = sha.hexdigest()
        return c_sign == sign

    def decrypt_phone(self, encryptedData, iv, session_key):
        """
        解密手机
        :param encryptedData:
        :param iv:
        :param session_key:
        :return:
        """
        return self.decrypt(encryptedData, iv, session_key)

    def decrypt(self, encryptedData, iv, session_key):
        # base64 decode
        sessionKey = base64.b64decode(session_key)
        logger.info("sessionKey: %s" % sessionKey)
        logger.info(encryptedData)
        encryptedData = base64.b64decode(encryptedData)
        logger.info("len: %s" % len(encryptedData))
        padding_length = 4 - (len(iv) % 4)
        if padding_length < 4:
            iv += '=' * padding_length
        iv = base64.b64decode(iv)
        cipher = AES.new(sessionKey, AES.MODE_CBC, iv)
        pt = cipher.decrypt(encryptedData)
        logger.info("pt: %s" % pt)
        decrypted = json.loads(self._unpad(pt))
        logger.info("decrypted: %s" % decrypted)
        return decrypted

    def decrypt_msg(self, encryptedMsg):
        ct_key = self.component_key
        padding_length = 4 - (len(ct_key) % 4)
        if padding_length < 4:
            ct_key += '=' * padding_length
        ct_key = base64.b64decode(ct_key)
        encryptedData = base64.b64decode(encryptedMsg)
        iv = ct_key[:16]
        cipher = AES.new(ct_key, AES.MODE_CBC, iv)
        pt = cipher.decrypt(encryptedData)
        decrypted = json.loads(self._unpad(pt))
        return decrypted

    def _unpad(self, s):
        s1 = s[:-ord(s[len(s) - 1:])]
        return s1

    # @property
    # def component_access_token(self):
    #     with with_redis() as redis:
    #         component_access_token = redis.get(self.component_access_token_key)
    #         if not component_access_token:
    #             url = '{}/api/kshou/get_component_access_token/'.format(self.ks_third_url)
    #             resp = requests.get(url)
    #             if resp.status_code == 200:
    #                 ret = resp.json()
    #                 component_access_token = ret['component_access_token']
    #                 expire_in = ret['expire_in']
    #                 with with_redis() as redis:
    #                     redis.set(self.component_access_token_key, component_access_token)
    #                     redis.expire(self.component_access_token_key, int(expire_in))
    #     return component_access_token

    def get_authorizer_access_token(self):
        with with_redis() as redis:
            authorizer_access_token = redis.get(self.authorizer_access_token_key)
            if not authorizer_access_token:
                url = '{}/api/kshou/get_authorizer_access_token/'.format(self.ks_third_url)
                token = get_jwt(self.app_id, dict(authorized_app_id=self.app_id))
                resp = requests.get(url, params=dict(token=token, authorized_app_id=self.app_id))
                if resp.status_code == 200:
                    ret = resp.json()
                    authorizer_access_token = ret['authorizer_access_token']
                    expire_in = ret['expire_in']
                    with with_redis() as redis:
                        redis.set(self.authorizer_access_token_key, authorizer_access_token)
                        redis.expire(self.authorizer_access_token_key, int(expire_in))
                else:
                    logger.error('获取authorizer_access_token失败')
        return authorizer_access_token

    def get_common_third_url(self, url):
        authorizer_access_token = self.get_authorizer_access_token()
        if not authorizer_access_token:
            time.sleep(1)
            # 有可能同时调用导致失败
            authorizer_access_token = self.get_authorizer_access_token()
        return '{}?component_app_id={}&authorizer_access_token={}'.format(url, self.component_app_id,
                                                                          authorizer_access_token)

    def code2session(self, js_code):
        # 登录换取openid
        url = self.get_common_third_url('openapi/mp/tp/auth/code2session')
        ret = self._get(url, params={"js_code": js_code})
        return ret

    def get_poi_list(self, key_word, city):
        # poi查询接口
        url = self.get_common_third_url('/openapi/mp/developer/poi/service/list')
        ret = self._get(url, params={"key_word": key_word, "city": city})
        return ret

    def poi_mount(self, poi_id, notify_url, quality_labels=None, grade_label=None, attach='', is_update=False):
        # https://mp.kuaishou.com/docs/develop/IndustrySolutions/introduction/saas/poiMount.html
        # POI申请挂载权限接口
        if is_update:
            url = self.get_common_third_url('/openapi/mp/developer/poi/service/update')
        else:
            url = self.get_common_third_url('/openapi/mp/developer/poi/service/mount')
        params = dict(poi_id=poi_id, notify_url=notify_url, quality_labels=quality_labels,
                      grade_label=grade_label, attach=attach)
        logger.debug(params)
        logger.debug(url)
        ret = self._post(url, params=params)
        # 是否需要审核
        need_auth = True
        if is_update:
            need_auth = ret['data']['needAudit']
        return ret, need_auth

    def poi_check(self, poi_ids: list):
        url = self.get_common_third_url('/openapi/mp/developer/poi/service/status')
        ret = self._post(url, params=dict(poi_ids=poi_ids))
        return ret

    def product_mount(self, poi_id: str, product_id: str, name: str, category_id: str, cover: str, path: str,
                      start_at: datetime,
                      end_at: datetime, full_price: int, sold_count: int, promotion_commission_rate: int,
                      notify_url: str, marketing_labels: list, is_update=False):
        from common.utils import get_timestamp
        # 商品首次上传/审核未通过重新上传, 商品对接接口
        # app_id + poi_id + product_id 需要保证唯一
        url = self.get_common_third_url('/openapi/mp/developer/poi/service/product/mount')
        # 小程序商品编辑接口调用条件：商品处于上线/下线状态注：1、若上一次编辑仍处于审核中，则将覆盖上一次进审信息
        # 2、商品信息编辑不会影响当前商品的状态（上线/下线），编辑审核未通过时也不会影响商品本身状态
        if is_update:
            url = self.get_common_third_url('/openapi/mp/developer/poi/service/product/update')
        # full_price 需*100转成分传入
        enable_promotion = False
        if promotion_commission_rate > 0:
            enable_promotion = True
        data = {
            "poi_id": poi_id,  # 想要挂载的POI的id
            "product_id": product_id,
            "name": name,
            "product_specific_category": category_id,  # 商品类目代码
            "cover": cover,  # 商品封面url
            "path": path,  # 卡片跳转路径
            "sell_expire_start_time": get_timestamp(start_at),  # 商品售卖有效期，起止时间
            "sell_expire_end_time": get_timestamp(end_at),  # 商品售卖有效期，截止时间
            "full_price": full_price,  # 商品原价，单位分
            "discount_price": full_price,  # 团购折扣价，单位分
            "refund_limit": 2,  # 1：过期退-随时退，2：有条件退
            "reserve_limit": 1,  # 1：免预约，2：需预约
            # "use_limit": 1, # 使用限制条件
            "sold_count": sold_count,  # 销量
            # "quality_labels" : quality_labels,  #商品品质标签
            "marketing_labels": marketing_labels,  # 商品营销活动标签
            "enable_promotion": enable_promotion,  # 是否分销推广
            "promotion_commission_rate": promotion_commission_rate,  # 分销佣金比例，万分数，必须为整数
            "attach": self.app_id,  # 附加信息，由开发者自定义
            "notify_url": notify_url  # 回调地址，必选参数
        }
        ret = self._post(url, params=data)
        return ret

    def update_product_status(self, poi_id, product_id, status):
        # 更新的状态，1：上线，0：下线
        url = self.get_common_third_url('/openapi/mp/developer/poi/service/product/status/update')
        self._post(url, params=dict(poi_id=poi_id, product_id=product_id, status=status))

    def check_service_status(self, param: list):
        # 小程序商品挂载状态查询接口
        url = self.get_common_third_url('/openapi/mp/developer/poi/product/service/status')
        return self._post(url, params={"param": param})

    def get_order_sign(self, params):
        params['component_app_id'] = self.component_app_id
        # logger.debug(params)
        pp = sorted(params.items(), key=lambda x: x[0])
        content = "&".join(["=".join(str(v) for v in list(item)) for item in pp]) + self.component_app_secret
        # logger.debug(content)
        params.pop('component_app_id')
        return md5(content.encode('utf-8')).hexdigest()

    def create_order(self, out_order_no: str, open_id: str, total_amount: float, show_name: str, detail: str,
                     expire_time: int, attach: str, notify_url: str,
                     goods_id: str, goods_detail_url: str, multiply: int, ty=1290):
        # attach 传用户opendid 方便识别
        # https://mp.kuaishou.com/docs/operate/platformAgreement/epayServiceCharge.html type 查询
        url = self.get_common_third_url('/openapi/mp/tp/epay/create_order')
        from common.utils import get_timestamp
        multi_copies_goods_info = [{"copies": multiply}]
        params = dict(out_order_no=out_order_no, open_id=open_id, total_amount=int(total_amount * 100),
                      subject=show_name,
                      detail=detail, type=ty, expire_time=expire_time, attach=attach,
                      notify_url=notify_url, goods_id=goods_id, goods_detail_url=goods_detail_url,
                      multi_copies_goods_info=json.dumps(multi_copies_goods_info))
        params['sign'] = self.get_order_sign(params)
        logger.error(params)
        ret = self._post(url, params=params)
        """
        "order_info":{
            "order_no":"121072611585202788127",
            "order_info_token": "****"
        }
        """
        return ret['order_info']

    def query_status(self, out_order_no):
        url = self.get_common_third_url('/openapi/mp/tp/epay/query_order')
        params = dict(out_order_no=out_order_no)
        params['sign'] = self.get_order_sign(params)
        ret = self._post(url, params=params)
        # 快手查单没有返回支付单号，只有回调有
        """
        extra_info字段为订单信息的来源，以JSON字符串格式。开发者可通过该字段区分订单来源于直播
        "payment_info":{
        "total_amount": 1200,
        "pay_status": "PROCESSING", // PROCESSING-处理中|SUCCESS-成功|FAILED-失败|TIMEOUT-超时
        "pay_time": ,
        "pay_channel": "WECHAT", // WECHAT-微信 | ALIPAY-支付宝
        "out_order_no": "1637808229728demo",
        "ks_order_no": "121112500031787702250",
        "extra_info":"{"url":"","item_type":"VIDEO","item_id":"5239375269605736845","author_id":"123"}", // VIDEO-视频|LIVE-直播|UNKNOWN-其他，url只有视频存在
        "enable_promotion": true,
        "promotion_amount": 1,
        "open_id":"5b748c61ef280130c0656638ebd4eaa6"}
        """
        payment_info = ret['payment_info']
        if payment_info['pay_status'] == 'SUCCESS':
            return True, payment_info
        return False, None

    def apply_refund(self, out_order_no, out_refund_no, reason, notify_url, refund_amount, multiply, attach):
        # attach 传用户opendid 方便识别
        url = self.get_common_third_url('/openapi/mp/tp/epay/apply_refund')
        multi_copies_goods_info = [{"copies": multiply}]
        params = dict(out_order_no=out_order_no, out_refund_no=out_refund_no, reason=reason, notify_url=notify_url,
                      refund_amount=refund_amount, attach=attach, multi_copies_goods_info=json.dumps(multi_copies_goods_info))
        params['sign'] = self.get_order_sign(params)
        ret = self._post(url, params=params)
        """
        {
            "result":1,
            "error_msg":"错误信息提示",
            "refund_no": "221072611585202788127"
        }
        """
        return ret['refund_no']

    def query_refund(self, out_refund_no):
        url = self.get_common_third_url('/openapi/mp/tp/epay/query_refund')
        params = dict(out_refund_no=out_refund_no)
        params['sign'] = self.get_order_sign(params)
        ret = self._post(url, params=params)
        """
        {
            "result":1,
            "error_msg":"success",
            "refund_info":{
                "ks_order_no":"122081801105480677436",
                "refund_status":"REFUND_SUCCESS",
                REFUND_PROCESSING-处理中，REFUND_SUCCESS-成功，REFUND_FAILED-失败
                "refund_no":"1660811124083refund",
                "ks_refund_type":"保证金账户退款",
                "refund_amount":1,
                "ks_refund_fail_reason":"账户异常",
                "apply_refund_reason":"用户申请退款",
                "ks_refund_no":"222081811172813537436"
            }
        }
        """
        return ret['refund_info']

    def order_settle(self, out_order_no, out_settle_no, reason, notify_url, settle_amount, multiply, attach):
        multi_copies_goods_info = json.dumps([{"copies": multiply}])
        url = self.get_common_third_url('/openapi/mp/tp/epay/settle')
        params = dict(out_order_no=out_order_no, out_settle_no=out_settle_no, reason=reason, notify_url=notify_url,
                      settle_amount=settle_amount, attach=attach,
                      multi_copies_goods_info=multi_copies_goods_info)
        params['sign'] = self.get_order_sign(params)
        ret = self._post(url, params=params)
        return ret['settle_no']

    def query_settle(self, out_settle_no):
        # 开发者的结算单号
        url = self.get_common_third_url('/openapi/mp/tp/epay/query_settle')
        params = dict(out_settle_no=out_settle_no)
        params['sign'] = self.get_order_sign(params)
        ret = self._post(url, params=params)
        """
        {
            "result":1,
            "error_msg":"错误提示信息",
            "settle_info":{
                "settle_no":"234325456565",
                "total_amount":3234, // 支付订单总金额
                "settle_amount":234, // 结算后给商家的金额
                "settle_status": "SETTLE_PROCESSING",
                "ks_order_no": "121120711774457276553",
                "ks_settle_no": "321120700415719078553"
                "promotion_amount": 0, //结算给带货达人的金额
                "developer_promotion_amount": 1 //结算给服务商的金额
            }
        }
        """
        return ret['settle_info']

    def order_report(self, out_order_no: str, open_id: str, order_create_time: datetime, order_status: int,
                     order_path: str, product_cover_img_id: str, poi_id: str, product_id: str,
                     product_catalog_code: str, product_city: str):
        """
        1	待支付
        2	支付成功
        3	已取消
        4	退款中
        5	退款失败
        6	退款成功
        10	待使用	虚拟类商品状态，含团购券待核销等状态
        11	已使用	虚拟类商品状态，含团购券已核销等状态
        """
        params = {
            "out_order_no": out_order_no,  # 订单号
            "out_biz_order_no": out_order_no,
            "open_id": open_id,
            "order_create_time": get_timestamp(order_create_time),  # 订单创建时间
            "order_status": order_status,
            "order_path": order_path,
            # "order_backup_url": order_backup_url, # 订单备用h5链接
            "product_cover_img_id": product_cover_img_id,  # 商品图对应的imgId
            "poi_id": poi_id,
            "product_id": product_id,
            "product_catalog_code": product_catalog_code,  # 商品类目代码
            "product_city": product_city  # poi的城市 河北省石家庄市裕华区
        }
        url = self.get_common_third_url('/openapi/mp/tp/order/v1/report')
        ret = self._post(url, params=params)
        return ret

    def upload_image(self, img_url):
        from django.utils.http import urlencode
        url = self.get_common_third_url('/openapi/mp/tp/file/img/uploadWithUrl')
        url = '{}&{}'.format(url, urlencode(dict(url=img_url)))
        ret = self._post(url)
        return ret['data']['imgId']


class KShouLife:
    API_BASE_URL = 'https://lbs-open.kuaishou.com/'

    def __init__(self):
        # 第三方没用过这个
        from kuaishou_wxa.models import KShouLife
        life = KShouLife.get()
        self.app_id = life.app_id
        self.app_secret = life.app_secret
        self.access_token_key = self.get_redis_key('life_access_token_key_{}'.format(self.app_id))
        self.refresh_token_key = self.get_redis_key('life_refresh_token_key_{}'.format(self.app_id))

    def get_redis_key(self, key):
        config = get_config()
        prefix = config['redis']['prefix']
        return '{}_{}'.format(prefix, key)

    def set_token(self, ret):
        with with_redis() as redis:
            # 要确认时候每次刷新token都会刷新refresh_token
            redis.set(self.access_token_key, ret['access_token'])
            redis.expire(self.access_token_key, ret['expires_in'] - 100)
            redis.set(self.refresh_token_key, ret['refresh_token'])
            # 180天过期，当 refresh_token过期之后，当用户再次使用时,需要第三方主动引导用户再次授权，一般不会，除非180天没调用接口
            redis.expire(self.refresh_token_key, ret['refresh_token_expires_in'] - 100)

    def set_access_token(self, code):
        url = '{}oauth2/access_token'.format(self.API_BASE_URL)
        resp = requests.get(url,
                            params=dict(app_id=self.app_id, grant_type='code', code=code, app_secret=self.app_secret))
        if resp.status_code == 200:
            ret = resp.json()
            if ret['result'] == 1:
                self.set_token(ret)

    def refresh_access_token(self):
        url = '{}oauth2/refresh_token'.format(self.API_BASE_URL)
        with with_redis() as redis:
            refresh_token = redis.get(self.refresh_token_key)
        if not refresh_token:
            msg = 'refresh_token无效，请重新在快手本地生活平台授权'
            logger.error(msg)
            raise ValidationError(msg)
        resp = requests.get(url,
                            params=dict(app_id=self.app_id, grant_type='refresh_token', refresh_token=refresh_token,
                                        app_secret=self.app_secret))
        if resp.status_code == 200:
            ret = resp.json()
            if ret['result'] == 1:
                self.set_token(ret)

    @property
    def access_token(self):
        with with_redis() as redis:
            access_token = redis.get(self.access_token_key)
            if not access_token:
                self.refresh_access_token()
            access_token = redis.get(self.access_token_key)
        return access_token


_ks_wxa = None
_ks_life = None


def get_ks_wxa():
    global _ks_wxa
    if not _ks_wxa:
        _ks_wxa = KShouWxa()
    return _ks_wxa


def get_ks_life():
    global _ks_life
    if not _ks_life:
        _ks_life = KShouLife()
    return _ks_life
