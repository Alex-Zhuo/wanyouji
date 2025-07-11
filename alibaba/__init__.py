# coding: utf-8
import os
import sys

from typing import List

from alibabacloud_dytnsapi20200217.client import Client as Dytnsapi20200217Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dytnsapi20200217 import models as dytnsapi_20200217_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
import logging

logger = logging.getLogger(__name__)


class CertNoImpl(object):
    def __init__(self):
        from common.config import get_config
        conf = get_config().get('alibaba_sms')
        self.access_key_id = conf['access_id']
        self.access_key_secret = conf['access_secret']
        self.endpoint = conf['endpoint_cert']
        self.auth_code = conf['auth_code']

    def create_client(self) -> Dytnsapi20200217Client:
        """
        使用AK&SK初始化账号Client
        @return: Client
        @throws Exception
        """
        # 工程代码泄露可能会导致 AccessKey 泄露，并威胁账号下所有资源的安全性。以下代码示例仅供参考。
        # 建议使用更安全的 STS 方式，更多鉴权访问方式请参见：https://help.aliyun.com/document_detail/378659.html。
        config = open_api_models.Config(
            # 必填，请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_ID。,
            access_key_id=self.access_key_id,
            # 必填，请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_SECRET。,
            access_key_secret=self.access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/Dytnsapi
        config.endpoint = self.endpoint
        return Dytnsapi20200217Client(config)

    def cert_no_verify(self, cert_name: str, cert_no: str):
        client = self.create_client()
        cert_no_request = dytnsapi_20200217_models.CertNoTwoElementVerificationRequest(
            auth_code=self.auth_code,
            cert_name=cert_name,
            cert_no=cert_no)
        try:
            resp = client.cert_no_two_element_verification(cert_no_request)
            ret = resp.to_map()
            logger.error(ret)
            if ret['statusCode'] == 200:
                data = ret['body']
                if data['Code'] == "OK":
                    if data['Data']['IsConsistent'] == '1':
                        return True
            return False
        except Exception as error:
            # 如有需要，请打印 error
            logger.error(error)
            # UtilClient.assert_as_string(error)
            return False

    def check_cert_no(self, cert_name: str, cert_no: str):
        from alibaba.api_limit import QPS_Queue
        ret = False
        with QPS_Queue('dxm-api-limit', 150, 1, 3) as got:
            if got:
                ret = self.cert_no_verify(cert_name, cert_no)
        return ret


_alibaba_cert = None


def get_inst():
    global _alibaba_cert
    if not _alibaba_cert:
        _alibaba_cert = CertNoImpl()
    return _alibaba_cert
