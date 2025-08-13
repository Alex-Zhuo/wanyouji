# coding: utf-8
import json
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.faceid.v20180301 import faceid_client, models as face_models
from tencentcloud.sms.v20210111 import sms_client, models as sms_models
import uuid, ssl, hmac, base64, hashlib
from datetime import datetime as pydatetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import logging
from caches import get_pika_redis
import json, requests
from urllib.error import HTTPError
from streaming.utils import create_streaming_response, api_response_stream_generator

logger = logging.getLogger(__name__)


class TencentCloudImpl(object):
    def __init__(self):
        from common.config import get_config
        conf = get_config().get('tencent')
        self.secret_key = conf['SecretKey']
        self.secret_id = conf['SecretId']
        self.cred = credential.Credential(self.secret_id, self.secret_key)
        self.appid = conf.get('appid')
        self.sign = conf.get('sign')
        self.template = conf.get('template')
        # 快递
        self.express_secret_key = conf['express_secret_key']
        self.express_secret_id = conf['express_secret_id']
        # 腾讯智能体配置
        self.agent_token = conf['agent_token']
        self.assistant_id = conf['assistant_id']
        self.agent_url = conf['agent_url']

    def cert_no_verify(self, cert_name: str, cert_no: str):
        try:
            cred = self.cred
            params = dict(IdCard=cert_no, Name=cert_name)
            httpProfile = HttpProfile()
            httpProfile.endpoint = "faceid.tencentcloudapi.com"
            # 实例化一个client选项，可选的，没有特殊需求可以跳过
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            # 实例化要请求产品的client对象,clientProfile是可选的
            client = faceid_client.FaceidClient(cred, "", clientProfile)

            # 实例化一个请求对象,每个接口都会对应一个request对象
            req = face_models.IdCardVerificationRequest()
            req.from_json_string(json.dumps(params))

            # 返回的resp是一个IdCardVerificationResponse的实例，与请求对象对应
            resp = client.IdCardVerification(req)
            # 输出json格式的字符串回包
            resp = json.loads(resp.to_json_string())
            logger.debug(resp)
            if resp['Result'] in ["0", 0]:
                return True
            return False

        except TencentCloudSDKException as err:
            logger.error(err)
            return False

    def smsvrcode(self, data):
        try:
            cred = self.cred
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
            req = sms_models.SendSmsRequest()

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

    def check_cert_no(self, cert_name: str, cert_no: str):
        from concu.api_limit import QPS_Queue
        ret = False
        with QPS_Queue('dxm-api-limit', 150, 1, 3) as got:
            if got:
                ret = self.cert_no_verify(cert_name, cert_no)
        return ret

    def express_query(self, number: str, mobile: str = "", expressCode: str = "auto"):
        """
        https://market.cloud.tencent.com/products/28085?keyword=%E5%BF%AB%E9%80%92
        number 快递单号
        mobile 查顺丰、中通时要输入寄件人或收件人手机号
        expressCode 快递代号 自动识别请传 auto
        """
        # 签名
        datetime = pydatetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        signStr = "x-date: %s" % (datetime)
        sign = base64.b64encode(
            hmac.new(self.express_secret_key.encode('utf-8'), signStr.encode('utf-8'), hashlib.sha1).digest())
        auth = '{"id": "%s", "x-date": "%s" , "signature": "%s"}' % (
            self.express_secret_id, datetime, sign.decode('utf-8'))
        # 请求方法
        method = 'POST'
        # 请求头
        headers = {
            'request-id': str(uuid.uuid1()),
            'Authorization': auth,
        }
        # 查询参数
        queryParams = {
            "expressCode": expressCode,
            "mobile": mobile,
            "number": number
        }
        # body参数（POST方法下存在）
        bodyParams = {
        }
        bodyParamStr = urlencode(bodyParams)
        # url参数拼接
        url = 'https://ap-shanghai.cloudmarket-apigw.com/service-ootu039r/express/query/v1'
        if len(queryParams.keys()) > 0:
            url = url + '?' + urlencode(queryParams)
        request = Request(url, headers=headers)
        request.get_method = lambda: method
        if method in ('POST', 'PUT', 'PATCH'):
            request.data = bodyParamStr.encode('utf-8')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            response = urlopen(request, context=ctx)
            content = response.read()
            if content:
                return content.decode('utf-8')
        except Exception as e:
            logger.error(e)
        return

    def query_express(self, order_id, number: str, mobile: str = ""):
        """
        快递公司code
        """
        try:
            name = 'query_express'
            key = '%s_%s' % (number, order_id)
            with get_pika_redis() as redis:
                st = False
                data = redis.hget(name, key)
                logger.error(data)
                if not data:
                    content = self.express_query(number, mobile)
                    if content:
                        content = json.loads(content)
                        if content['code'] == 200:
                            data = content['data']
                            if data['status'] in [1, 2]:
                                timeout = 2 * 3600
                            elif data['status'] == 3:
                                # 已签收,结果保存30天
                                timeout = 30 * 24 * 3600
                            else:
                                timeout = 6 * 24 * 3600
                            redis.hset(name, key, json.dumps(data))
                        else:
                            logger.error('error express: %s, %s' % (key, content))
                            timeout = 30 * 3600
                            redis.hset(name, key, content['msg'])
                        redis.expire(key, int(timeout))
                        st = True
                    else:
                        data = '接口获取失败'
                else:
                    data = json.loads(data)
                return st, data
        except HTTPError as e:
            return False, dict(msg=u'请求快递服务异常')
        except ValueError:
            return False, dict(msg=u'请求快递服务异常')
        except (requests.Timeout):
            return False, dict(msg=u'请求快递服务超时')

    def agent_request(self, method: str, user_id: int, content: str, params: dict=None):
        """POST请求 - 流式调用外部API"""
        api_url = self.agent_url
        headers = {
            'X-Source': 'openapi',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.agent_token)
        }
        data = {
            "assistant_id": self.assistant_id,
            "user_id": str(user_id),
            "stream": True,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            ]
        }
        generator = api_response_stream_generator(
            api_url=api_url,
            method=method,
            headers=headers,
            data=data,
            params=params
        )

        return create_streaming_response(generator, 'text/plain; charset=utf-8')


_tent_xun = None


def get_tencent():
    global _tent_xun
    if not _tent_xun:
        _tent_xun = TencentCloudImpl()
    return _tent_xun
