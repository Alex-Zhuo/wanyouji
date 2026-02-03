# coding: utf-8
import logging

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
# 导入可选配置类
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
# 导入对应产品模块的client models。
from tencentcloud.sms.v20190711 import sms_client, models

from common.config import get_config
from typing import List

from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient

from qcloud import TencentCloudImpl

logger = logging.getLogger(__name__)
import json


class ISms:
    def smsvrcode(self, request):
        """
        短信验证码
        :param request: dict
        :return:
        """
        raise NotImplementedError()


class QCloudSmsImpl(TencentCloudImpl):

    def smsvrcode(self, data):
        try:
            cred = self.cred
            # cred = credential.Credential(
            #     os.environ.get(""),
            #     os.environ.get("")
            # )

            # 实例化一个http选项，可选的，没有特殊需求可以跳过。
            httpProfile = HttpProfile()
            httpProfile.reqMethod = "POST"  # post请求(默认为post请求)
            httpProfile.reqTimeout = 30  # 请求超时时间，单位为秒(默认60秒)
            httpProfile.endpoint = "sms.tencentcloudapi.com"  # 指定接入地域域名(默认就近接入)

            # 非必要步骤:
            # 实例化一个客户端配置对象，可以指定超时时间等配置
            clientProfile = ClientProfile()
            clientProfile.signMethod = "TC3-HMAC-SHA256"  # 指定签名算法
            clientProfile.language = "en-US"
            clientProfile.httpProfile = httpProfile

            # 实例化要请求产品(以sms为例)的client对象
            # 第二个参数是地域信息，可以直接填写字符串ap-guangzhou，或者引用预设的常量
            client = sms_client.SmsClient(cred, "ap-guangzhou", clientProfile)

            # 实例化一个请求对象，根据调用的接口和实际情况，可以进一步设置请求参数
            # 你可以直接查询SDK源码确定SendSmsRequest有哪些属性可以设置
            # 属性可能是基本类型，也可能引用了另一个数据结构
            # 推荐使用IDE进行开发，可以方便的跳转查阅各个接口和数据结构的文档说明
            req = models.SendSmsRequest()

            # 基本类型的设置:
            # SDK采用的是指针风格指定参数，即使对于基本类型你也需要用指针来对参数赋值。
            # SDK提供对基本类型的指针引用封装函数
            # 帮助链接：
            # 短信控制台: https://console.cloud.tencent.com/sms/smslist
            # sms helper: https://cloud.tencent.com/document/product/382/3773

            # 短信应用ID: 短信SdkAppid在 [短信控制台] 添加应用后生成的实际SdkAppid，示例如1400006666
            req.SmsSdkAppid = self.appid
            # 短信签名内容: 使用 UTF-8 编码，必须填写已审核通过的签名，签名信息可登录 [短信控制台] 查看
            req.Sign = self.sign
            # 短信码号扩展号: 默认未开通，如需开通请联系 [sms helper]
            req.ExtendCode = ""
            # 用户的 session 内容: 可以携带用户侧 ID 等上下文信息，server 会原样返回
            req.SessionContext = ""
            # 国际/港澳台短信 senderid: 国内短信填空，默认未开通，如需开通请联系 [sms helper]
            req.SenderId = ""
            # 下发手机号码，采用 e.164 标准，+[国家或地区码][手机号]
            # 示例如：+8613711112222， 其中前面有一个+号 ，86为国家码，13711112222为手机号，最多不要超过200个手机号
            req.PhoneNumberSet = ["+86{}".format(data['mobile'])]
            # 模板 ID: 必须填写已审核通过的模板 ID。模板ID可登录 [短信控制台] 查看
            req.TemplateID = self.template
            # 模板参数: 若无模板参数，则设置为空
            req.TemplateParamSet = [data['code'], data['timeout']]

            # 通过client对象调用DescribeInstances方法发起请求。注意请求方法名与请求对象是对应的。
            # 返回的resp是一个DescribeInstancesResponse类的实例，与请求对象对应。
            logger.debug(req)

            def _send():
                '''
                只考虑发一条的情况
                """

            succeed:
{"SendStatusSet": [{"SerialNo": "
2028:f825de8f0747639f4100", "PhoneNumber": "+8615577150426", "Fee": 1, "SessionContext": "", "Code": "Ok", "Message": "send success", "IsoCode": "CN"}], "RequestId": "49486560-5b
7d-4bda-9e94-299eda7289a0"}
            ],
            "RequestId": "8469d26a-2ad3-400d-a833-dfd962342a72"
             }

             failed:

             {'SendStatusSet': [{'SerialNo': '', 'PhoneNumber': '+8615296376320',
             'Fee': 0, 'SessionContext': '', 'Code': 'LimitExceeded.PhoneNumberDailyLimit',
             'Message': 'the number of sms messages sent from a single mobile number every day exceeds the upper limit',
             'IsoCode': 'CN'}], 'RequestId': '3c1293ec-daa5-42f9-9f2c-ba3118031853'}
            """
                :return:
                '''
                return client.SendSms(req)

            resp = _send()
            logger.debug(resp)
            resp = json.loads(resp.to_json_string(indent=2))
            # logger.debug(resp)
            # code = resp['SendStatusSet'][0]['Code']
            # logger.debug(f'{code}')
            # 输出json格式的字符串回包
            if resp['SendStatusSet'][0]['Code'] == "Ok":
                return True
            else:
                logger.warning(resp)
                return False
        except TencentCloudSDKException as err:
            logger.error(err)
            return False


class AlibabacloudSmsImpl(ISms):
    def __init__(self):
        conf = get_config().get('alibaba_sms')
        self.access_key_id = conf['access_id']
        self.access_key_secret = conf['access_secret']
        self.endpoint = conf['endpoint']
        self.signName = conf['signName']
        self.template_code = conf['template_code']
        self.template_login_code = conf['template_login_code']
        self.template_mz_code = conf['template_mz_code']
        self.template_ticket_code = conf['template_ticket_code']

    def create_client(self) -> Dysmsapi20170525Client:
        """
        使用AK&SK初始化账号Client
        @param access_key_id:
        @param access_key_secret:
        @return: Client
        @throws Exception
        """
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=self.access_key_id,
            # 必填，您的 AccessKey Secret,
            access_key_secret=self.access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/Dysmsapi
        config.endpoint = self.endpoint
        return Dysmsapi20170525Client(config)

    def smsvrcode(self, data):
        # 请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_ID 和 ALIBABA_CLOUD_ACCESS_KEY_SECRET。
        # 工程代码泄露可能会导致 AccessKey 泄露，并威胁账号下所有资源的安全性。以下代码示例使用环境变量获取 AccessKey 的方式进行调用，仅供参考，建议使用更安全的 STS 方式，更多鉴权访问方式请参见：https://help.aliyun.com/document_detail/378659.html
        import json
        client = self.create_client()
        template_code = None
        template_param = None
        if data.get('biz'):
            if data['biz'] == 'mz':
                template_code = self.template_mz_code
                template_param = json.dumps(dict(name=data['name'], reason=data['reason']))
            elif data['biz'] == 'lock_seat':
                template_code = self.template_ticket_code
                data['name'] = data['name'].replace('【', '')
                data['name'] = data['name'].replace('】', '')
                name = '{}...'.format(data['name'][:10]) if len(data['name']) > 10 else data['name']
                template_param = json.dumps(dict(name=name, code=data['code'], time=data['time']))
        else:
            if data.get('code'):
                template_code = self.template_login_code
                template_param = json.dumps(dict(code=data['code']))
            else:
                template_code = self.template_code
                data['name'] = data['name'].replace('【', '')
                data['name'] = data['name'].replace('】', '')
                name = '{}...'.format(data['name'][:10]) if len(data['name']) > 10 else data['name']
                template_param = json.dumps(dict(name=name, number=data['number'], time=data['time']))
        if not (template_code and template_param):
            return False
        send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
            phone_numbers=data['mobile'],
            sign_name=self.signName,
            template_code=template_code,
            template_param=template_param
        )
        try:
            # 复制代码运行请自行打印 API 的返回值
            resp = client.send_sms_with_options(send_sms_request, util_models.RuntimeOptions())
            logger.debug(resp)
        except Exception as error:
            # 如有需要，请打印 error
            logger.error(error)
            UtilClient.assert_as_string(error)
            return False
        return True


_tencent = None
_alibaba = None


def get_sms():
    from qcloud import get_tencent
    return get_tencent()
