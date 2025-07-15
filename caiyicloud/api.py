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

    def get_product(self, page: int = 1, page_size: int = 50):
        """
        该接口用于获取已授权的节目列表
        https://platform.caiyicloud.com/#/doc/v1/distribution/event/events
        """
        headers = self.headers()
        headers['sign'] = self.get_sign(headers)
        params = dict(supplier_id=self.supplier_id, page=page, page_size=page_size)
        ret = self._get('api/event/v1/events', params=params, headers=headers)
        self.parse_resp(ret)
        return ret['data']


_caiyicloud = None


def get_caiyi_cloud():
    global _caiyicloud
    if not _caiyicloud:
        _caiyicloud = CaiYiCloud()
    return _caiyicloud
