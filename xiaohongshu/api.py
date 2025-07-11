# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import requests
from Crypto.Cipher import AES
import logging
from xiaohongshu.exceptions import XhsClientException, APILimitedException
import base64
import json
from caches import with_redis
from django.utils import timezone
import string
from random import sample
from datetime import datetime
from common.utils import get_config
from typing import List, Dict

logger = logging.getLogger(__name__)


def random_string(length=16):
    rule = string.ascii_letters + string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


class XhsWxaAbstract(object):
    API_BASE_URL = 'https://miniapp.xiaohongshu.com/'

    def _request(self, method, url_or_endpoint, params=None, data=None, headers=None, **kwargs):
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
            res = requests.post(url, params=params, json=data, headers=headers)
        else:
            res = requests.get(url, params=params, headers=headers)
        try:
            res.raise_for_status()
        except requests.RequestException as reqe:
            raise XhsClientException(
                errcode=None,
                errmsg=None,
                client=self,
                request=reqe.request,
                response=reqe.response)
        ret_data = json.loads(res.content.decode('utf-8', 'ignore'), strict=False)
        # logger.error(ret_data)
        # if ret_data['code'] != 0 or not ret_data['success']:
        #     logger.error(ret_data)
        #     raise APILimitedException(
        #         errcode=ret_data['code'],
        #         errmsg=ret_data['error_msg'],
        #         client=self,
        #         request=res.request,
        #         response=res)
        return ret_data, res

    def parse_resp(self, ret_data: dict, res):
        if ret_data['code'] != 0 or not ret_data['success']:
            logger.error(ret_data)
            raise APILimitedException(
                errcode=ret_data['code'],
                errmsg=ret_data['msg'],
                client=self,
                request=res.request,
                response=res)

    def _get(self, url, params=None, headers=None, **kwargs):
        return self._request(
            method='get',
            url_or_endpoint=url,
            params=params,
            headers=headers,
            **kwargs
        )

    def _post(self, url, params=None, data=None, headers=None, **kwargs):
        return self._request(
            method='post',
            url_or_endpoint=url,
            params=params,
            data=data,
            headers=headers,
            **kwargs
        )


class XiaoHongShuWxa(XhsWxaAbstract):

    def __init__(self):
        from xiaohongshu.models import XiaoHongShuWxa
        xsh_wxa = XiaoHongShuWxa.get()
        self.app_id = xsh_wxa.app_id
        self.app_secret = xsh_wxa.app_secret
        self.access_token_key = self.get_redis_key('xhs_ac_token')
        self.s_token = xsh_wxa.s_token
        self.encodingAesKey = xsh_wxa.encodingAesKey

    def get_redis_key(self, key):
        config = get_config()
        prefix = config['redis']['prefix']
        return '{}_{}'.format(prefix, key)

    def check_sign(self, timestamp: str, nonce: str, sign: str, encrypt: str = None):
        """
        encrypt: str, timestamp: str, nonce: str 回调返回
        """
        from xiaohongshu.XshMsgCrypt import SHA1
        sha1 = SHA1()
        ret, signature = sha1.getSHA1(self.s_token, timestamp, nonce, encrypt)
        return signature == sign

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
        ct_key = self.encodingAesKey
        padding_length = 4 - (len(ct_key) % 4)
        if padding_length < 4:
            ct_key += '=' * padding_length
        ct_key = base64.b64decode(ct_key)
        encryptedData = base64.b64decode(encryptedMsg)
        iv = ct_key[:16]
        cipher = AES.new(ct_key, AES.MODE_CBC, iv)
        pt = cipher.decrypt(encryptedData)
        pt = self._unpad(pt)
        length = self.recover_bytes(pt[16:20])
        # byte数组截去真实消息后，末尾剩下的字符就是appid
        # pt[length + 21:] appid
        decrypted = json.loads(pt[20:length + 20])
        return decrypted

    def recover_bytes(self, data: bytes):
        source_number = 0
        length = 4
        number = 8
        i = 0
        while i < length:
            source_number <<= number
            source_number |= data[i] & 0xff
            i += 1
        return source_number

    def _unpad(self, s):
        s1 = s[:-ord(s[len(s) - 1:])]
        return s1

    @property
    def access_token(self):
        """
        获取应用调用凭证
        """
        with with_redis() as redis:
            access_token = redis.get(self.access_token_key)
            if not access_token:
                ret, res = self._post('api/rmp/token', data={"appid": self.app_id, "secret": self.app_secret})
                self.parse_resp(ret, res)
                data = ret['data']
                access_token = data['access_token']
                expire_in = data['expire_in']
                with with_redis() as redis:
                    redis.set(self.access_token_key, access_token)
                    redis.expire(self.access_token_key, int(expire_in))
        return access_token

    def common_params(self):
        """
        公共请求参数
        """
        return dict(app_id=self.app_id, access_token=self.access_token)

    def code2session(self, code):
        """
        登录code2Session
        """
        params = self.common_params()
        params['code'] = code
        ret, res = self._get('api/rmp/session', params)
        self.parse_resp(ret, res)
        return ret['data']

    def get_qrcode_unlimited(self, scene, page=None, width=430):
        """
        获取不限制的小程序二维码
        https://miniapp.xiaohongshu.com/docsV2/doc/DC164497
        """
        params = self.common_params()
        params['appid'] = params.pop('app_id')
        url = '{}api/rmp/qrcode/unlimited'.format(self.API_BASE_URL)
        data = dict(scene=scene, page=page, width=width)
        resp = requests.post(url, params=params, json=data)
        if resp.status_code == 200:
            from io import BytesIO
            buf = BytesIO()
            buf.write(resp.content)
            buf.flush()
            return buf

    def category_search(self, category_name: str, force_category_v2=True):
        """
        搜索可用类目:休闲娱乐-演出-专业剧场
        https://miniapp.xiaohongshu.com/docsV2/doc/DC274768
        """
        params = self.common_params()
        data = dict()
        data['category_name'] = category_name
        data['force_category_v2'] = force_category_v2
        ret, res = self._post('api/rmp/mp/deal/category/search', params=params, data=data)
        self.parse_resp(ret, res)
        return ret['data']

    def apps_category(self):
        """获取小程序设置的工业类目"""
        params = self.common_params()
        ret, res = self._get('api/rmp/apps/category', params=params)
        self.parse_resp(ret, res)
        return ret['data']

    def get_product(self, out_product_id: str):
        """
        商品-获取信息
        out_product_id:外部商品id
        https://miniapp.xiaohongshu.com/docs?path=/docs/api-backend/post-api-rmp-mp-deal-product-get
        """
        params = self.common_params()
        data = dict()
        data['out_product_id'] = out_product_id
        ret, res = self._post('api/rmp/mp/deal/product/get', params=params, data=data)
        self.parse_resp(ret, res)
        return ret['data']

    def upsert_product(self, out_product_id: str, name: str, short_title: str, desc: str, category_id: str,
                       top_image: str, path: str,
                       create_at: datetime, skus: List[Dict], poi_id_list: list, product_type=1, settle_type=1):
        """
        https://miniapp.xiaohongshu.com/docsV2/doc/DC886309#anchorId-%E5%85%AC%E5%85%B1%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0
        product_type 1-团购，2-酒旅预售券，3-酒旅日历商品
        settle_type 结算方式，1-总店结算，2-门店结算，3-区域结算，开通担保支付的商家下必传，使用门店或区域结算的前提是已认领门店并提交了门店资质
        "skus": [
            {
              "out_sku_id": "string",
              "name": "string",
              "sku_image": "string",
              "origin_price": 0,
              "sale_price": 0,
              "status": 0  状态：1：上架，0：下架，2：系统下架，如果不填，默认：1
            }
        ]
        """
        from common.utils import get_timestamp
        biz_create_time = int(get_timestamp(create_at) / 1000)
        biz_update_time = int(get_timestamp(timezone.now()) / 1000)
        params = self.common_params()
        data = {
            "out_product_id": out_product_id,
            "name": name,
            "short_title": short_title,
            "desc": desc,
            "path": path,
            "top_image": top_image,
            "category_id": category_id,
            "biz_create_time": biz_create_time,
            "biz_update_time": biz_update_time,
            "skus": skus,
            "product_type": product_type,
            "settle_type": settle_type,
            "poi_id_list": poi_id_list
        }
        ret, res = self._post('api/rmp/mp/deal/poi/product/upsert', params=params, data=data)
        self.parse_resp(ret, res)
        return ret

    def home_page_item_tab(self, out_spu_ids: list):
        """
        专业号主页商品排序
        is_apply 是否开启自定义排序 0:否 1:是
        """
        params = self.common_params()
        data = {
            "is_apply": 0
        }
        i = 1
        for out_spu_id in out_spu_ids:
            key = 'out_spu_id_{}'.format(i)
            data[key] = out_spu_id
            i += 1
            # 最多6个
            if i >= 7:
                break
        ret, res = self._post('api/rmp/display/home_page_item_tab', params=params, data=data)
        self.parse_resp(ret, res)
        return ret['data']

    def batch_change_sku_status(self, status: int, out_sku_ids: list):
        """
        status，1：上架，0：下架
        外部sku商品id集合,sku 商品全部下架，对应的 product 自动下架
        """
        params = self.common_params()
        data = dict()
        data['out_sku_ids'] = out_sku_ids
        if status == 1:
            url = 'api/rmp/mp/deal/product/sku/batch_online'
        else:
            url = 'api/rmp/mp/deal/product/sku/batch_offline'
        ret, res = self._post(url, params=params, data=data)
        self.parse_resp(ret, res)
        return ret

    def order_upsert(self, out_order_id: str, open_id: str, path: str, create_at: datetime, expire_at: datetime,
                     product_infos: List[Dict], order_price: int, freight_price: int = 0, discount_price: int = 0):
        """
        关于商品
        请确保下单的商品，都已经通过【商品-新增/删除】接口同步成功并且是上架状态
        关于订单价格计算
        单个商品的 real_price 价格等于 sale_price 减去所有 discount_infos 价格之和
        订单总价 order_price 等于所有商品的 real_price 价格总和加上 freight_price 价格，再加上所有 extra_price_infos 的价格总和
        关于返回结果 pay_token 过期时间和订单过期时间保持一致，如果订单修改，返回新的 pay_token，过期时间不变
        path 订单详情页的小程序路径，/开头
        order_price: 分
        product_infos:[
        {
            "out_product_id": out_product_id,
            "out_sku_id": "string",
            "num": 0,
            "sale_price": 0,
            "real_price": 0,
            "image": "string",
            "discount_infos": [
                {
                    "name": "string",
                    "price": 0,
                    "num": 0
                }
            ]
        }
        ]
        """
        params = self.common_params()
        from common.utils import get_timestamp
        biz_create_time = int(get_timestamp(create_at) / 1000)
        order_expired_time = int(get_timestamp(expire_at) / 1000)
        biz_update_time = int(get_timestamp(timezone.now()) / 1000)
        data = {
            "out_order_id": out_order_id,
            "open_id": open_id,
            "path": path,
            "biz_create_time": biz_create_time,
            "biz_update_time": biz_update_time,
            "order_expired_time": order_expired_time,
            "product_infos": product_infos,
            "price_info": {
                "order_price": order_price,
                "freight_price": freight_price,
                "discount_price": discount_price,
                # "extra_price_infos": [
                #     {
                #         "name": "string",
                #         "price": 0,
                #         "num": 0,
                #         "biz_id": "string",
                #         "biz_type": "string"
                #     }
                # ]
            }
        }
        logger.info(data)
        ret, res = self._post('api/rmp/mp/deal/order/upsert', params=params, data=data)
        self.parse_resp(ret, res)
        return ret['data']

    def query_pay_token(self, out_order_id: str, open_id: str):
        """
        获取订单支付token
        """
        params = self.common_params()
        data = {
            "out_order_id": out_order_id,
            "open_id": open_id
        }
        ret, res = self._post('api/rmp/mp/deal/query_pay_token', params=params, data=data)
        self.parse_resp(ret, res)
        return ret['data']

    def sync_status(self, status: int, out_order_id: str, open_id: str):
        """
        订单-状态同步
        状态：2：已支付，6：已发货，7：已完成，71：已关闭，998：已取消
        """
        params = self.common_params()
        from common.utils import get_timestamp
        biz_update_time = int(get_timestamp(timezone.now()) / 1000)
        data = {
            "status": status,
            "out_order_id": out_order_id,
            "biz_update_time": biz_update_time,
            "open_id": open_id
        }
        ret, res = self._post('api/rmp/mp/deal/order/sync_status', params=params, data=data)
        self.parse_resp(ret, res)
        return ret

    def order_detail(self, out_order_id: str, open_id: str, order_type: int = 1):
        """
        https://miniapp.xiaohongshu.com/docsV2/doc/DC510914
        订单详情
        订单状态，1：待支付，6：已支付，7：已完成（订单走到终态，进入结算流程），71：已关闭，998：已取消
        order_type 1: 主单（预售券/团购券） 2：预约单（预售券/日历订单
        voucher_status 核销状态 1：待使用 2：已使用 3：已作废(全额退款) 4：已冻结(比如一张券发起了预约，此时商家未接单)
        """
        params = self.common_params()
        data = {
            "order_type": order_type,
            "out_order_id": out_order_id,
            "open_id": open_id
        }
        ret, res = self._post('api/rmp/mp/deal/gpay_order/get', params=params, data=data)
        # self.parse_resp(ret, res)
        return ret

    def verify_code(self, out_order_id: str, voucher_infos: List[Dict], poi_id: str = None):
        """
        凭证核销
        poi_id 门店id，订单的商品是分账到门店的商品，必传
        "voucher_infos":[
            {
                "voucher_code":"string"
            }
        ]
        """
        params = self.common_params()
        data = {
            "out_order_id": out_order_id,
            "poi_id": poi_id,
            "voucher_infos": voucher_infos
        }
        ret, res = self._post('api/rmp/mp/deal/voucher/verify', params=params, data=data)
        return ret

    def create_refund(self, out_order_id: str, out_refund_no: str, open_id: str, create_at: datetime, refund_price: int,
                      product_infos: List[Dict], refund_voucher_detail: List[Dict], reason: str = None):
        """
        开发者通过本接口发起退款，支持整单退，部分退
        交易时间超过 1 年的订单无法提交退款
        如果退款需要审核，请结合auto_confirm+”同步售后单状态“接口一起使用
        售后类型：1：退款，2：退款退货
        product_type 商品类型，1=团购券，2=预售券，3=日历商品，担保支付必填
         "product_infos": [
                {
                    "out_product_id": out_product_id,
                    "out_sku_id": out_sku_id,
                    "num": 0,
                    "price": 0  退商品价格，该商品退货价格之和，单位（分）
                }
            ]
        "refund_voucher_detail": [
            {
                "voucher_code": "string", 凭证ID
                "refund_price": 0  退款价格，单位到（分） int
            }
        ]
        """
        params = self.common_params()
        from common.utils import get_timestamp
        biz_create_time = int(get_timestamp(create_at) / 1000)
        data = {
            "out_order_id": out_order_id,
            "out_after_sales_order_id": out_refund_no,
            "open_id": open_id,
            "type": 1,
            "reason": reason,
            "biz_create_time": biz_create_time,
            "price_info": {
                "refund_price": refund_price,  # 售后单-退款总价
                # "freight_price": 0,
                # "extra_price_infos": [
                #     {
                #         "name": "string",
                #         "price": 0,
                #         "num": 0
                #     }
                # ]
            },
            "product_infos": product_infos,
            "refund_voucher_detail": refund_voucher_detail,
            "product_type": 1,
            "auto_confirm": True  # false-需要二次商家确认 true-不需要商家确认，直接发起退款
        }
        ret, res = self._post('api/rmp/mp/deal/order/after_sales_order/add', params=params, data=data)
        self.parse_resp(ret, res)
        return ret

    def query_refund(self, out_refund_no: str, open_id: str, out_order_id: str = None):
        """
        获取售后订单详情
        status 售后单状态，1-处理中 2-成功 3-失败
        """
        params = self.common_params()
        data = {
            "out_order_id": out_order_id,
            "out_after_sales_order_id": out_refund_no,
            "open_id": open_id
        }
        ret, res = self._post('api/rmp/mp/deal/order/after_sales_order/get', params=params, data=data)
        return ret

    def check_settle_info(self, order_id: str):
        """
        https://miniapp.xiaohongshu.com/docsV2/doc/DC497536
        结算明细查询
        transaction_settle_status 0:不需要结算，1:初始化，2：可结算，3：结算中，4：已结算，5：结算失败，6：结算冲抵
        """
        params = self.common_params()
        data = {
            "order_id": order_id
            # "seller_id":"string",
            # "settle_start_time":0,
            # "settle_start_to":0,
            # "page_num":0,
            # "page_size":0,
            # "settle_biz_type":0,
            # "common_settle_status":0
        }
        ret, res = self._post('api/rmp/mp/deal/check_settle_info', params=params, data=data)
        self.parse_resp(ret, res)
        return ret

    def poi_list(self, page_no=1, page_size=100):
        """
        获取专业号绑定的POI信息
        page_size: 最大100
        """
        params = self.common_params()
        params['page_no'] = page_no
        params['page_size'] = page_size
        ret, res = self._get('api/rmp/mp/deal/poi/list', params=params)
        self.parse_resp(ret, res)
        return ret

    # def query_commission(self, out_order_id: str, out_product_id: str, open_id: str):
    #     """
    #     担保支付订单不支持该查询
    #
    #     查询达人带货预估佣金率
    #     https://miniapp.xiaohongshu.com/docs?path=/docs/api-backend/post-api-rmp-mp-deal-query_commission
    #     is_cps	是否为达人带货 0:否 1:是
    #     commission_rate	达人佣金率,单位(整型/万分之)
    #     distributor_name 达人加密名称
    #     cps_type int 带货类型
    #     """
    #     params = self.common_params()
    #     data = {
    #         "out_order_id": out_order_id,
    #         "out_product_id": out_product_id,
    #         "open_id": open_id
    #     }
    #     ret, res = self._post('api/rmp/mp/deal/query_commission', params=params, data=data)
    #     self.parse_resp(ret, res)
    #     return ret['data']


_xhs_wxa = None


def get_xhs_wxa():
    global _xhs_wxa
    if not _xhs_wxa:
        _xhs_wxa = XiaoHongShuWxa()
    return _xhs_wxa
