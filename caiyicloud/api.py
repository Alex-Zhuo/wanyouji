# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import requests
from Crypto.Cipher import AES
import logging
import base64
import json
from caches import with_redis
from django.utils import timezone
import string
from random import sample
from datetime import datetime
from caiyicloud.error_codes import CaiYiCloudClientException, create_exception_from_error_code, is_success
from common.utils import get_config
from typing import List, Dict
from requests import Response
import uuid

logger = logging.getLogger(__name__)


def random_string(length=16):
    rule = string.ascii_letters + string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


class CaiYiCloudAbstract(object):
    API_BASE_URL = 'https://openapi-qad.caiyicloud.com/'

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
            raise CaiYiCloudClientException(
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
        return ret_data

    def parse_resp(self, ret_data: dict):
        error_code = ret_data["code"]
        if not is_success(error_code):
            exception = create_exception_from_error_code(
                error_code,
                request_data={"test": "data"},
                response_data=ret_data
            )
            raise exception

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


class CaiYiCloud(CaiYiCloudAbstract):
    """
    文档链接
    https://platform.caiyicloud.com/#/doc/v1/distribution/event/events
    """

    def __init__(self):
        from caiyicloud.models import CaiYiCloudApp
        caiyi = CaiYiCloudApp.get()
        self.app_id = caiyi.app_id
        self.supplier_id = caiyi.supplier_id
        self.private_key = caiyi.private_key

    def get_redis_key(self, key):
        config = get_config()
        prefix = config['redis']['prefix']
        return '{}_{}'.format(prefix, key)

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

    def headers(self):
        """
        公共请求参数
        """
        from common.utils import get_timestamp
        timestamp = int(get_timestamp(timezone.now()))
        return dict(app_id=self.app_id, timestamp=str(timestamp))

    def get_sign(self, params: Dict) -> str:
        from caiyicloud.sign_utils import sign_top_request
        return sign_top_request(params, self.private_key)

    def common_sign_params(self, params: dict):
        p = params.copy()
        p['supplier_id'] = self.supplier_id
        return p

    def get_events(self, page: int = 1, page_size: int = 50):
        """
        该接口用于获取已授权的节目列表
        """
        headers = self.headers()
        headers['sign'] = self.get_sign(headers)
        params = dict(supplier_id=self.supplier_id, page=page, page_size=page_size)
        ret = self._get('api/event/v1/events', params=params, headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def event_detail(self, event_id: str, auth_type=0):
        """
        该接口用于获取已授权的节目详细信息
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        headers['sign'] = self.get_sign(sign_params)
        params = dict(supplier_id=self.supplier_id, auth_type=auth_type)
        ret = self._get(f'api/event/v1/events/:{event_id}', params=params, headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def venue_detail(self, venue_id: str):
        """
        该接口用于查询场馆信息
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        headers['sign'] = self.get_sign(sign_params)
        ret = self._get(f'api/venue/v1/venues/:{venue_id}', headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def sessions_list(self, event_id: str, session_id: str = None, page: int = 1, page_size: int = 50):
        """
        该接口用于获取已授权的场次列表信息
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        headers['sign'] = self.get_sign(sign_params)
        params = dict(supplier_id=self.supplier_id, session_id=session_id, page=page, page_size=page_size)
        ret = self._get(f'api/event/v1/events/:{event_id}/sessions', params=params, headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def ticket_types(self, session_ids: list):
        """
        该接口用于获取可授权的可售场次票价信息。常见问题答疑。
        不允许跨节目查询
        票面为套票情况下，需分销套票关联基础票，否则套票信息无法查出
        session_ids: 场次id集合，最大20
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        headers['sign'] = self.get_sign(sign_params)
        params = dict(supplier_id=self.supplier_id)
        data = dict(session_ids=session_ids)
        ret = self._post('api/event/v1/ticket_types/query', params=params, data=data, headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def ticket_stock(self, session_ids: list):
        """
        该接口用于获取可授权的场次的票价库存信息。常见问题答疑。
        仅返回可售的票价库存
        不允许跨节目查询
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        headers['sign'] = self.get_sign(sign_params)
        params = dict(supplier_id=self.supplier_id)
        data = dict(session_ids=session_ids)
        ret = self._post('api/event/v1/inventories/query', params=params, data=data, headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def seat_url(self, event_id: str, session_id: str, ticket_type_id: str, navigate_url: str,
                 display_ticket_type_ids: list):
        """
        该接口用于获取选座H5的UR
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        headers['sign'] = self.get_sign(sign_params)
        request_id = uuid.uuid4().hex
        params = dict(supplier_id=self.supplier_id)
        data = dict(event_id=event_id, session_id=session_id, ticket_type_id=ticket_type_id, request_id=request_id,
                    navigate_url=navigate_url, display_ticket_type_ids=display_ticket_type_ids)
        ret = self._post('api/event/v1/ticket_types/url', params=params, data=data, headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def seat_info(self, biz_id: str):
        """
        选座后回调返回的biz_id，查询
        该接口用于获取指定区域的可售座位编号
        """
        headers = self.headers()
        headers['sign'] = self.get_sign(headers)
        ret = self._post(f'api/event/v1/sessions/seat_info?biz_id={biz_id}')
        self.parse_resp(ret)
        return ret['data']

    def orders_create(self, external_order_no: str, original_total_amount: float, actual_total_amount: float,
                      buyer_cellphone: str, ticket_list: list, id_info: dict = None, promotion_list: list = None,
                      address_info: dict = None, express_amount: float = 0):
        """
        文档 https://platform.caiyicloud.com/#/doc/v1/distribution/order/create
        该接口用于创建订单
        订单实名信息，一单一证时必填：
        证件号,姓名,1：身份证
        id_info= dict(number=id_card, name=name,type=1)

        promotion_list 优惠信息,一笔订单只能命中一个营销活动，不允许传多个不同的营销活动id 详情看文档
        promotion_list = [
        # 满减 type优惠类型,1:满额立减;2:每满立减;3:满件打折;4:满额打折;5:每满件立减;6:满件立减
            {
              "type": 1,
              "discount_amount": 1
            }
          ]
        # 快递票使用
        "address_info": {
                "contact_name": "张三",
                "contact_cellphone": "13212341234",
                "province_code": "31",
                "city_code": "01",
                "district_code": "01",
                "address": "上海黄埔区"
        }
        #
        "ticket_list": [
                {
                    "event_id": "62b2d83cc2f13200015eb51e", # 节目id
                    "session_id": "62b2d851c2f13200015eb544", # 场次id
                    "delivery_method": 2, # 配送方式，2：电子票（直刷入场）；4：快递票；8：（电子票）现场取票；32：电子票（身份证直刷入场）；64:身份证换票；
                    "ticket_type_id": "62b2d90ac2f13200015eb5e7", # 票档id
                    "ticket_category": 2, # 类别，1：基础票，2：固定套 3：自由套
                    "qty": 1, #购买票品数量（基础票为基础票张数，套票为套票套数）
                    #座位信息/套票信息/一票一证实名信息
                    "seats": [
                        {
                            "id": "62b2d90bb6f33e00013b6bb8",  # 座位id(座位接口中返回seat_concrete_id)选座必填
                            "seat_group_id": "62b2d90aaa23a8000121e8a0" # 套票票组合id，套票必填,一套套票中该字段值需相同。
                            选座/非选座套票下单均需要填，长度小于等于32
                        },
                    ]
                    # 票实名信息，一票一证时必填（选座/非选座项目均需要）
                    id_info: {number=身份证, name=姓名,type=1,cellphone=手机号}
                }
            ]
        return
        {
            "code": "000000",
            "msg": "success",
            "trace_id": "81792471b881991c",
            "data": {
                "order_no":"CY12123132",
                "auto_cancel_order_time":"2022-06-06 12:10:00"
            }
        }
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        sign_params['external_order_no'] = external_order_no
        headers['sign'] = self.get_sign(sign_params)
        params = dict(supplier_id=self.supplier_id)
        data = {
            "external_order_no": external_order_no,  # 订单号
            "original_total_amount": original_total_amount,  # 原总价格
            "express_amount": express_amount,  # 配送价格
            "actual_total_amount": actual_total_amount,  # 实付金额
            "buyer_cellphone": buyer_cellphone,  # 购票人手机号
            "ticket_list": ticket_list
        }
        if id_info:
            data['id_info'] = id_info
        if promotion_list:
            data['promotion_list'] = promotion_list
        if address_info:
            data['address_info'] = address_info
        ret = self._post('api/event/v1/ticket_types/url', params=params, data=data, headers=headers)
        self.parse_resp(ret)
        return ret['data']

    def order_detail(self, external_order_no: str = None, order_no: str = None):
        """
        该接口用于查询订单详细信息
        external_order_no 和 order_no 二选一
        """
        headers = self.headers()
        sign_params = self.common_sign_params(headers)
        headers['sign'] = self.get_sign(sign_params)
        params = dict(supplier_id=self.supplier_id, external_order_no=external_order_no, order_no=order_no)
        ret = self._get('api/order/v1/orders', params=params)
        self.parse_resp(ret)
        return ret['data']


_caiyicloud = None


def get_caiyi_cloud():
    global _caiyicloud
    if not _caiyicloud:
        _caiyicloud = CaiYiCloud()
    return _caiyicloud
