# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import requests
from optionaldict import optionaldict

from common.config import get_config
import logging
from douyin.exceptions import TikTokClientException, APILimitedException
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Cryptodome.Hash import MD5, SHA256
import base64
import warnings
import uuid
import json
from caches import with_redis
import os
from hashlib import md5
from django.utils import timezone
import string
from random import sample
from datetime import datetime

logger = logging.getLogger(__name__)
from common.utils import get_timestamp


def random_string(length=16):
    rule = string.ascii_letters + string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


class TikTokAbstract(object):
    API_BASE_URL = 'https://open.douyin.com/'

    def get_client_token(self, refresh=False):
        return True

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
        # res = requests.request(
        #     method=method,
        #     url=url,
        #     json=params,
        #     **kwargs
        # )
        if method == 'post':
            res = requests.post(url, json=params, headers=headers)
        else:
            res = requests.get(url, params=params, headers=headers)
        try:
            res.raise_for_status()
        except requests.RequestException as reqe:
            raise TikTokClientException(
                errcode=None,
                errmsg=None,
                client=self,
                request=reqe.request,
                response=reqe.response)
        result = json.loads(res.content.decode('utf-8', 'ignore'), strict=False)
        # logger.error(result)
        if 'data' in result or result.get('err_no'):
            error_code = None
            if result.get('data'):
                error_code = result['data'].get('error_code')
            if error_code is not None:
                if error_code != 0:
                    if error_code == 2190008:
                        self.get_client_token(True)
                    logger.error(result)
                    errmsg = result['data']['description']
                    if result.get('extra'):
                        errmsg = '{},{}'.format(result['data']['description'], result['extra']['sub_description'])
                    raise APILimitedException(
                        errcode=result['data']['error_code'],
                        errmsg=errmsg,
                        client=self,
                        request=res.request,
                        response=res)
            else:
                err_no = result.get('err_no')
                if err_no != 0:
                    logger.error(result)
                    raise APILimitedException(
                        errcode=result['err_no'],
                        errmsg=result['err_msg'],
                        client=self,
                        request=res.request,
                        response=res)
        return result['data']

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

    def get_sign(self, method, uri, timestamp, nonce_str, http_body):
        """
        参考例子
        https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/develop/server/signature-algorithm
        HTTP请求方法\nURL\n请求时间戳\n请求随机串\n请求报文主体\n
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data = method + '\n' + uri + '\n' + timestamp + "\n" + nonce_str + "\n" + http_body + "\n"
        # data = "POST\n/abc\n1680835692\ngjjRNfQlzoDIJtVDOfUe\n{\"eventTime\":1677653869000,\"status\":102}\n"
        data = data.replace(' ', '')
        with open(os.path.join(base_dir, 'private_key.pem')) as f:
            priKey = RSA.importKey(f.read())
            signer = PKCS1_v1_5.new(priKey)
            # hash_obj = SHA256.new(data.encode('utf-8'))
            # signature = base64.b64encode(signer.sign(hash_obj)).decode('utf8')
            # return signature
            digest = SHA256.new()
            digest.update(data.encode())
            sign = signer.sign(digest)
            signature = base64.b64encode(sign)
            return signature

    def check_sign(self, http_body, timestamp, nonce_str, sign):
        """
        参考例子
        https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/develop/server/signature-algorithm
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data = "{}\n{}\n{}\n".format(timestamp, nonce_str, http_body)
        data = data.replace(' ', '')
        # logger.error(data)
        with open(os.path.join(base_dir, 'platform_public_key.pem')) as f:
            public_key = RSA.importKey(f.read())
            verifier = PKCS1_v1_5.new(public_key)
            digest = SHA256.new()
            digest.update(data.encode())
            is_verify = verifier.verify(digest, base64.b64decode(sign))
            # hash_obj = SHA256.new(data.encode('utf-8'))
            # ret =  signer.verify(hash_obj, base64.b64decode(sign))
            return is_verify

    def check_sign_new(self, http_body, timestamp, nonce_str, sign):
        """
        参考例子
        https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/develop/server/signature-algorithm
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data = "{}\n{}\n{}\n".format(timestamp, nonce_str, http_body)
        # logger.error(data)
        with open(os.path.join(base_dir, 'platform_public_key.pem')) as f:
            public_key = RSA.importKey(f.read())
            verifier = PKCS1_v1_5.new(public_key)
            digest = SHA256.new()
            digest.update(data.encode())
            is_verify = verifier.verify(digest, base64.b64decode(sign))
            # hash_obj = SHA256.new(data.encode('utf-8'))
            # ret =  signer.verify(hash_obj, base64.b64decode(sign))
            return is_verify


class DouYin(TikTokAbstract):

    # 抖音平台
    def __init__(self):
        from mp.models import SystemDouYin
        dy = SystemDouYin.get()
        self.account_name = dy.account_name
        self.account_id = dy.account_id
        self.client_key = dy.client_key
        self.client_secret = dy.client_secret
        self.client_token_key = 'pl{}_{}'.format(self.client_key, self.client_secret[:3])

    def get_header(self):
        header = dict()
        header['access-token'] = self.client_token
        header['Content-Type'] = 'application/json'
        return header

    def get_access_token(self, code):
        resp = self._post('oauth/access_token/',
                          params={
                              "grant_type": "authorization_code",
                              "client_key": self.client_key,
                              "client_secret": self.client_secret,
                              "code": code})
        return resp

    def refresh_client_token(self):
        res = self._post('oauth/client_token/',
                         params={
                             "grant_type": "client_credential",
                             "client_key": self.client_key,
                             "client_secret": self.client_secret})
        return res['access_token'], res['expires_in'] - 10

    def get_client_token(self, refresh=False):
        with with_redis() as redis:
            client_token = redis.get(self.client_token_key)
            if not client_token or refresh:
                client_token, expires_in = self.refresh_client_token()
                redis.set(self.client_token_key, client_token)
                redis.expire(self.client_token_key, expires_in)
        return client_token

    @property
    def client_token(self):
        return self.get_client_token()

    def get_qual(self, page_index=1):
        """
        飞书上的
        https://bytedance.larkoffice.com/docx/BzZDdNLBAoB5T7xNk8McBtD3nCh
        """
        url = 'goodlife/v1/account/qual/search/?account_id={}&access_token={}'.format(self.account_id,
                                                                                      self.client_token)
        params = {
            "data": {
                "parent_life_account_ids": [],
                "accurate_life_account_ids": [],
                "qual_ids": [],
                "qual_name": "",
                "data_access": {
                    "need_effective_qual": True,
                    "only_store_account_qual": True
                },
                "page_index": page_index,
                "page_size": 200  # 分页-每页大小，最大为200
            }
        }
        resp = self._post(url, params=params)
        return resp

    def get_category(self, category_id=0, query_category_type=0):
        headers = self.get_header()
        params = dict(account_id=self.account_id, category_id=category_id, query_category_type=query_category_type)
        resp = self._get('goodlife/v1/goods/category/get/', params=params, headers=headers)
        return resp['category_infos']

    def goods_template(self, category_id, product_type=1, product_sub_type=None):
        """
        商品类型：1 : 团购套餐 3 : 预售券 4 : 日历房 5 : 门票 7 : 旅行跟拍 8 : 一日游 11 : 代金券 12:酒旅新预售 15：次卡
        """
        headers = self.get_header()
        params = dict(category_id=category_id, product_type=product_type, product_sub_type=product_sub_type)
        resp = self._get('goodlife/v1/goods/template/get/', params=params, headers=headers)
        return resp

    def goods_dy_create(self, params: dict) -> dict:
        """
        - 创建或更新商品
        - 对于同一服务商，相同的out_id会被认为是同一商品，重复创建会被覆盖(相当于修改)
        - 商品和SKU属性字段(attr_key_value_map )，需要通过商品模板接口获取
        - 新增商品二级类型参数 product_sub_type （仅小程序酒旅预售应用）
         https://open.douyin.com/goodlife/v1/goods/product/save/
        """
        headers = self.get_header()
        params['account_id'] = self.account_id
        params['product']['account_name'] = self.account_name
        print(params)
        resp = self._post('goodlife/v1/goods/product/save/', params=params, headers=headers)
        return resp

    def goods_operate(self, product_id, op_type):
        """
        op_type
        1-上线 2-下线
        """
        headers = self.get_header()
        params = dict()
        params['account_id'] = self.account_id
        params['product_id'] = product_id
        params['op_type'] = op_type
        resp = self._post('goodlife/v1/goods/product/operate/', params=params, headers=headers)
        return resp

    def skus_batch_save(self, params):
        """
        op_type
        1-上线 2-下线
        """
        headers = self.get_header()
        params['account_id'] = self.account_id
        resp = self._post('goodlife/v1/goods/sku/batch_save/', params=params, headers=headers)
        return resp

    def product_draft(self, params):
        """
        op_type
        1-上线 2-下线
        """
        headers = self.get_header()
        params['account_id'] = self.account_id
        resp = self._get('goodlife/v1/goods/product/draft/get/', params=params, headers=headers)
        return resp

    def product_free_audit(self, product_id, sold_end_time=None, stock_qty=0, change_stock=False):
        """
        - 免审修改团购活动
        sold_end_time 售卖结束时间，时间戳，单位秒
        stock_qty 总库存
        """
        headers = self.get_header()
        params = dict()
        params['account_id'] = self.account_id
        params['product_id'] = product_id
        if sold_end_time:
            from common.utils import get_timestamp
            params['sold_end_time'] = int(get_timestamp(sold_end_time) / 1000)
        if change_stock:
            params['stock_qty'] = stock_qty
        resp = self._get('goodlife/v1/goods/product/free_audit/', params=params, headers=headers)
        return resp

    def push_delivery(self, params):
        headers = self.get_header()
        resp = self._post('api/apps/trade/v2/fulfillment/push_delivery', params=params, headers=headers)
        return resp

    def push_delivery_new(self, params):
        headers = self.get_header()
        url = '{}api/apps/trade/v2/fulfillment/push_delivery'.format(self.API_BASE_URL)
        resp = requests.post(url, json=params, headers=headers)
        ret = resp.json()
        if ret.get('data'):
            if ret['data']['error_code'] == 0:
                return ret['data']
            else:
                logger.error(ret)
                return ret['extra']

    def create_refund(self, params: dict):
        """
        """
        uri = 'api/apps/trade/v2/refund/create_refund'
        headers = self.get_header()
        resp = self._post(uri, params=params, headers=headers)
        return resp

    def merchant_audit_callback(self, out_refund_no, refund_audit_status):
        """
        开发者使用该接口回传退款单的退款审核结果
        out_refund_no 开发者侧退款单号
        refund_audit_status 1：同意退款2：不同意退款
        """
        uri = 'api/apps/trade/v2/refund/merchant_audit_callback'
        headers = self.get_header()
        resp = self._post(uri, params=dict(out_refund_no=out_refund_no, refund_audit_status=refund_audit_status),
                          headers=headers)
        return resp

    def query_refund(self, refund_id):
        """
        查询退款
        """
        uri = 'api/apps/trade/v2/refund/query_refund'
        headers = self.get_header()
        resp = self._post(uri, params=dict(refund_id=refund_id), headers=headers)
        return resp

    def query_refund_order(self, order_id):
        """
        查询退款
        """
        uri = 'api/apps/trade/v2/refund/query_refund'
        headers = self.get_header()
        resp = self._post(uri, params=dict(order_id=order_id), headers=headers)
        return resp

    def query_status(self, out_order_no):
        """
        ret
        {'data': {'item_id': '', 'order_status': 'TIMEOUT', 'out_order_no': '20231116211129458639', 'refund_amount': 0,
        'channel_pay_id': '', 'cp_extra': '{"my_order_id":618}', 'message': '', 'order_id': 'ots73020468996269530123359',
         'payment_order_id': 'MECPN7302046921852651816', 'pay_channel': 0, 'total_fee': 24000, 'delivery_type': 0, 'pay_time': '',
         'seller_uid': '72789245768543296350', 'settle_amount': 0, 'error_code': 0, 'description': ''},
         'extra': {'error_code': 0, 'description': '', 'sub_error_code': 0,
        'sub_description': 'success', 'logid': '202311171139320E1C8F9A3B6F5F042D36', 'now': 1700192372}}
        """
        headers = self.get_header()
        params = dict(out_order_no=out_order_no)
        try:
            ret = self._post('api/apps/trade/v2/order/query_order', params=params, headers=headers)
            # order_id = resp['order_id']
            # ret = self.query_item_order_info(order_id)
            # ret['order_id'] = order_id
            if ret['order_status'] == 'SUCCESS' and ret['error_code'] == 0 and ret['channel_pay_id']:
                return True, ret['channel_pay_id']
            else:
                return False, None
        except Exception as e:
            return False, None

    def query_item_order_info(self, order_id):
        headers = self.get_header()
        params = dict(order_id=order_id)
        resp = self._post('api/apps/trade/v2/order/query_item_order_info', params=params, headers=headers)
        return resp

    def list_plan_by_spuid(self, spu_id):
        # 查询通用佣金计划
        headers = self.get_header()
        params = dict(page_no=1, page_size=10, spu_id=spu_id)
        resp = self._post('api/match/v2/poi/list_plan_by_spuid/', params=params, headers=headers)
        return resp

    def save_common_plan(self, commission_rate, content_type, spu_id, plan_id=0):
        # 发布/修改通用佣金计划
        headers = self.get_header()
        params = dict(commission_rate=commission_rate, content_type=content_type, spu_id=spu_id, plan_id=plan_id)
        resp = self._post('api/match/v2/poi/save_common_plan/', params=params, headers=headers)
        return resp

    def update_common_plan_status(self, plan_update_list: list):
        """
        修改通用佣金计划状态
        1：设置为进行中
        2：设置为暂停中
        3：设置为已关闭
         "plan_update_list": [
        {
            "plan_id": 7089050168758126636,
            "status": 1
        },]
        """
        headers = self.get_header()
        params = dict(plan_update_list=plan_update_list)
        resp = self._post('api/match/v2/poi/update_common_plan_status/', params=params, headers=headers)
        return resp

    def save_live_oriented_plan(self, plan_name, merchant_phone, douyin_id_list: list, product_list: list, plan_id=0):
        # 发布/修改直播间定向佣金计划
        headers = self.get_header()
        params = dict(plan_name=plan_name, merchant_phone=merchant_phone, douyin_id_list=douyin_id_list,
                      product_list=product_list, plan_id=plan_id)
        resp = self._post('api/match/v2/poi/save_live_oriented_plan/', params=params, headers=headers)
        return resp

    def save_video_oriented_plan(self, plan_name, commission_duration, merchant_phone,
                                 douyin_id_list: list, product_list: list, start_time=None, end_time=None, plan_id=0):
        # 发布/修改短视频定向佣金计划
        headers = self.get_header()
        params = dict(plan_name=plan_name, start_time=start_time, end_time=end_time,
                      commission_duration=commission_duration, merchant_phone=merchant_phone,
                      douyin_id_list=douyin_id_list,
                      product_list=product_list, plan_id=plan_id)
        resp = self._post('api/match/v2/poi/save_video_oriented_plan/', params=params, headers=headers)
        return resp

    def delete_oriented_plan_talent(self, plan_id, douyin_id):
        # 取消定向佣金计划指定的达人
        headers = self.get_header()
        params = dict(plan_id=plan_id, douyin_id=douyin_id)
        url = '{}api/match/v2/poi/delete_oriented_plan_talent/'.format(self.API_BASE_URL)
        resp = requests.post(url, json=params, headers=headers)
        ret = resp.json()
        if ret.get('err_no') != 0:
            return False, ret['err_msg']
        else:
            return True, resp

    def update_oriented_plan_status(self, plan_update_list: list):
        """
        修改定向佣金计划状态
        1：设置为进行中
        2：设置为暂停中
        3：设置为已关闭
        """
        headers = self.get_header()
        params = dict(plan_update_list=plan_update_list)
        url = '{}api/match/v2/poi/update_oriented_plan_status/'.format(self.API_BASE_URL)
        resp = requests.post(url, json=params, headers=headers)
        ret = resp.json()
        if ret.get('err_no') != 0:
            return False, ret['err_msg']
        else:
            return True, resp

    def oriented_plan_list(self, spu_id_list: list):
        """
        通过商品 ID 查询定向佣金计划
        """
        headers = self.get_header()
        params = dict(spu_id_list=spu_id_list)
        resp = self._post('api/match/v2/poi/oriented_plan_list/', params=params, headers=headers)
        return resp

    def query_cps(self, out_order_no: str):
        """
        查询CPS信息
        order_id：抖音订单号
        """
        headers = self.get_header()
        params = dict(out_order_no=out_order_no)
        url = '{}api/apps/trade/v2/order/query_cps'.format(self.API_BASE_URL)
        resp = requests.post(url, json=params, headers=headers)
        ret = resp.json()
        # logger.error(ret)
        if ret.get('data'):
            if ret['data']['error_code'] == 0:
                return True, ret
            else:
                return False, ret['data']['description']

    def censor_image(self, image_url):
        """
        查询CPS信息
        order_id：抖音订单号
        """
        headers = self.get_header()
        params = dict(image=image_url, app_id=self.client_key)
        url = '{}api/apps/v1/censor/image'.format(self.API_BASE_URL)
        resp = requests.post(url, json=params, headers=headers)
        if resp.status_code == 200:
            ret = resp.json()
            logger.error(ret)
            if ret['err_no'] == 0:
                for dd in ret['predicts']:
                    if dd['hit'] == True:
                        return False, self.translate_censor_image_name(dd['model_name'])
                return True, ''
        return False, '图片检验失败'

    def translate_censor_image_name(self, name):
        data = dict(anniversary_flag='特殊标志', porn="图片涉黄", cartoon_leader="领导人漫画", sensitive_flag='敏感旗帜',
                    sensitive_text='敏感文字',
                    leader_recognition='敏感人物', bloody="图片血腥", fandongtaibiao="未准入台标", plant_ppx='图片涉毒',
                    high_risk_social_event='社会事件', high_risk_boom='爆炸', high_risk_money="人民币",
                    high_risk_terrorist_uniform="极端服饰",
                    high_risk_sensitive_map='敏感地图', great_hall='大会堂', cartoon_porn='色情动漫',
                    party_founding_memorial='建党纪念',
                    )
        return data.get(name) or '敏感图片'

    def merchant_cancel_book(self, book_id, cancel_reason):
        """
        商家取消预约
        """
        headers = self.get_header()
        params = dict(book_id=book_id, cancel_reason=cancel_reason)
        url = '{}api/apps/trade/v2/book/merchant_cancel_book'.format(self.API_BASE_URL)
        resp = requests.post(url, json=params, headers=headers)
        if resp.status_code == 200:
            ret = resp.json()
            if ret.get('extra'):
                if ret['extra']['error_code'] == 0:
                    return True, None
                else:
                    return False, ret['extra']['sub_description']
        return False, '接口错误'

    def query_book(self, order_id):
        """
        查询预约单信息
        """
        headers = self.get_header()
        params = dict(order_id=order_id)
        url = '{}api/apps/trade/v2/book/query_book'.format(self.API_BASE_URL)
        resp = requests.post(url, json=params, headers=headers)
        ret = resp.json()
        if resp.status_code == 200:
            if ret.get('extra'):
                if ret['extra']['error_code'] == 0 and ret.get('data'):
                    return True, ret['data']['book_info_list']
                else:
                    return False, ret['extra']['sub_description']
        return False, '接口错误'

    def create_book(self, order_id: str, out_book_no: str, open_id: str, item_book_info_list: list):
        """
        创建预约单
        """
        headers = self.get_header()
        params = {
            "order_id": order_id,  # 抖音侧订单号
            "out_book_no": out_book_no,  # 外部预约单号
            "open_id": open_id,
            "item_book_info_list": item_book_info_list
        }
        url = '{}api/apps/trade/v2/book/create_book'.format(self.API_BASE_URL)
        # logger.error('params,{}'.format(params))
        resp = requests.post(url, json=params, headers=headers)
        if resp.status_code == 200:
            ret = resp.json()
            logger.error('创建预约单,{}'.format(ret))
            if ret.get('extra'):
                if ret['extra']['error_code'] == 0 and ret.get('data'):
                    return True, ret['data']
                else:
                    return False, ret['extra']
        return False, '接口错误'


class TikTokWxa(TikTokAbstract):
    # 抖音小程序
    API_BASE_URL = 'https://developer.toutiao.com/'
    SAND_BOX_URL = 'https://open-sandbox.douyin.com/'
    SHOW_START_TEMPLATE_ID = 'MSG1630445719337279990310514493759'

    def __init__(self):
        """
        :param app_id
        :param secret
        """
        from mp.models import SystemDouYinMP
        dy_wxa = SystemDouYinMP.get()
        self.app_id = dy_wxa.app_id
        self.secret = dy_wxa.app_secret
        self.access_token_key = '{}_{}'.format(self.app_id, self.secret[:3])
        self.debug = False
        self.refund_token = dy_wxa.token
        self.salt = dy_wxa.salt

    def _request(self, method, url_or_endpoint, params=None, headers=None, **kwargs):
        uri = self.API_BASE_URL if not self.debug else self.SAND_BOX_URL
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
            raise TikTokClientException(
                errcode=None,
                errmsg=None,
                client=self,
                request=reqe.request,
                response=reqe.response)
        result = json.loads(res.content.decode('utf-8', 'ignore'), strict=False)
        if 'err_no' in result and result['err_no'] != 0:
            logger.error(result)
            raise APILimitedException(
                errcode=result['err_no'],
                errmsg=result['err_tips'],
                client=self,
                request=res.request,
                response=res)
        return result['data']

    def get_access_token(self):
        """获取 access_token
        :return: JSON 数据包
        """
        res = self._post('api/apps/v2/token',
                         params={
                             'appid': self.app_id,
                             'secret': self.secret,
                             'grant_type': 'client_credential'
                         })
        self.expires_in = res['expires_in'] - 10
        return res['access_token']

    @property
    def access_token(self):
        with with_redis() as redis:
            access_token = redis.get(self.access_token_key)
            if not access_token:
                access_token = self.get_access_token()
                redis.set(self.access_token_key, access_token)
                redis.expire(self.access_token_key, self.expires_in)
        return access_token

    def refresh_access_token(self):
        with with_redis() as redis:
            access_token = self.get_access_token()
            redis.set(self.access_token_key, access_token)
            redis.expire(self.access_token_key, self.expires_in)
        return access_token

    def get_openid(self, code):
        """
        通过login接口获取到登录凭证后，开发者可以通过服务器发送请求的方式获取 session_key 和 openid。
        """
        res = self._post('api/apps/v2/jscode2session',
                         params={
                             'appid': self.app_id,
                             'secret': self.secret,
                             'code': code,
                         })
        return res

    def send_notify(self, open_id, data, url):
        """
        发送模板消息
        """
        res = self._post('api/apps/subscribe_notification/developer/v1/notify', params={
            "access_token": self.access_token,
            "app_id": self.app_id,
            "tpl_id": TikTokWxa.SHOW_START_TEMPLATE_ID,
            "open_id": open_id,
            "data": data,
            "page": url})
        return res

    def get_qrcode(self, path):
        # dy = get_dou_yin()
        # headers = dy.get_header()
        # headers['content-type'] = 'application/json'
        params = dict(appname='douyin', path=path, access_token=self.access_token)
        resp = requests.post('https://developer.toutiao.com/api/apps/qrcode', json=params)
        if resp.status_code == 200:
            try:
                ret = resp.json()
                logger.error(ret)
                return False
            except Exception as e:
                import io
                return io.BytesIO(resp.content)
        logger.error('获取失败')
        return False

    def text_antidirt(self, content):
        headers = dict()
        headers['X-Token'] = self.access_token
        params = {
            "tasks": [
                {
                    "content": content
                }
            ]
        }
        resp = requests.post('https://developer.toutiao.com/api/v2/tags/text/antidirt', json=params, headers=headers)
        if resp.status_code == 200:
            ret = resp.json()
            if ret.get('error_id') and ret.get['code'] == 401:
                self.refresh_access_token()
                resp = requests.post('https://developer.toutiao.com/api/v2/tags/text/antidirt', json=params,
                                     headers=headers)
                ret = resp.json()
            if ret.get('data') and ret['data'][0]['code'] == 0 and not ret['data'][0]['predicts'][0]['hit']:
                return True
        return False

    def create_refund(self, params: dict):
        """
        """
        uri = 'api/apps/trade/v2/create_refund'
        headers = dict()
        headers['Content-Type'] = 'application/json'
        from common.utils import get_timestamp
        timestamp = int(get_timestamp(timezone.now()) / 1000)
        nonce_str = random_string(32)
        http_body = json.dumps(params, ensure_ascii=False)
        params['app_id'] = self.app_id
        headers['Byte-Authorization'] = self.get_sign('POST', '/' + uri, timestamp, nonce_str, http_body)
        resp = self._post(uri, params=params, headers=headers)
        return resp

    # def get_sign(self, params: dict):
    #     """
    #     担保交易签名
    #     https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/develop/server/ecpay/refund-list/refund
    #     """
    #     values = [self.salt]
    #     for k, v in params.items():
    #         values.append(v)
    #     s = '&'.join(sorted(values))
    #     logging.debug(s)
    #     m = md5()
    #     m.update(s.encode('utf-8'))
    #     sign = m.hexdigest()
    #     logger.debug(sign)
    #     return sign


_dou_yin = None
_tiktok = None


def get_dou_yin():
    global _dou_yin
    if not _dou_yin:
        _dou_yin = DouYin()
    return _dou_yin


def get_tiktok():
    global _tiktok
    if not _tiktok:
        _tiktok = TikTokWxa()
    return _tiktok
