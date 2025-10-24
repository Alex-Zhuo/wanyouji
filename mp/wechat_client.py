# coding: utf-8
import base64
import os
import logging
import json
import time

import pysnooper
from decouple import config
from django.conf import settings

import requests
from wechatpy import WeChatClient
from wechatpy.client.api import WeChatWxa
from wechatpy.exceptions import WeChatClientException
from urllib.parse import quote
import sys
from wechatpy.session.redisstorage import RedisStorage

from caches import get_redis
from mp.models import SystemMP, MsgTemplate, SystemWxMP
from mp.mp_config import use_open_platform
from mall.utils import random_string
from Crypto.Cipher import AES

log = logger = logging.getLogger(__name__)


class MpClientBase(object):
    _client = None

    def __new__(cls, *args, **kwargs):
        if cls._client is None:
            cls._client = super(cls.__class__, cls).__new__(cls)
        return cls._client

    def get_user_info(self, open_id):
        raise NotImplementedError()

    def send_text(self, open_id, msg):
        raise NotImplementedError()

    def get_action_qr_code(self, key, val):
        raise NotImplementedError()

    def get_template_id(self, template_short_id):
        raise NotImplementedError()

    def send_template_msg(self, open_id, template_id, data, url):
        raise NotImplementedError()

    def get_js_signature(self, url):
        raise NotImplementedError()

    def get_menu(self):
        raise NotImplementedError()

    def set_menu(self, data):
        raise NotImplementedError()

    def material(self, media_type, offset, count):
        raise NotImplementedError()

    def get_media(self, media_id, media_type, request=None):
        raise NotImplementedError()

    def set_industry(self, industry_1, industry_2):
        raise NotImplementedError()

    def get_industry(self):
        raise NotImplementedError()

    @property
    def template(self):
        raise NotImplementedError()


MP_SESSION_STORAGE = None
LP_SESSION_STORAGE = None


class MpClient(MpClientBase):
    def __init__(self):
        mp = SystemMP.get()
        if mp:
            global MP_SESSION_STORAGE
            if not MP_SESSION_STORAGE:
                MP_SESSION_STORAGE = RedisStorage(get_redis(), prefix='mp_client_session_%s_' % mp.app_id)
            self.wc_client = WeChatClient(mp.app_id, mp.app_secret, session=MP_SESSION_STORAGE)
        else:
            raise ValueError('先配置公众号')

    def get_industry(self):
        """
        获取行业
        :return:
        {
        "primary_industry":{"first_class":"运输与仓储","second_class":"快递"},
        "secondary_industry":{"first_class":"IT科技","second_class":"互联网|电子商务"}
        }
        """
        return self.wc_client.template.get_industry()

    @property
    def template(self):
        return self.wc_client.template

    def get_user_info(self, open_id):
        return self.wc_client.user.get(open_id)

    def send_text(self, open_id, msg):
        if open_id and msg:
            self.wc_client.message.send_text(open_id, msg)

    def get_action_qr_code(self, key, val):
        res = self.wc_client.qrcode.create({
            'action_name': 'QR_LIMIT_STR_SCENE',
            'action_info': {
                'scene': {'scene_str': json.dumps(dict(key=key, val=val))},
            }
        })
        if res:
            qr_url = self.wc_client.qrcode.get_url(res)
            return dict(url=qr_url)

    def get_qr_scene(self, id):
        res = self.wc_client.qrcode.create({
            'action_name': 'QR_SCENE',
            'expire_seconds': 2591000,
            'action_info': {
                'scene': {"scene_id": id},
            }
        })
        if res:
            qr_url = self.wc_client.qrcode.get_url(res)
            return dict(url=qr_url)

    def get_template_id(self, template_short_id):
        try:
            return self.wc_client.template.get(template_short_id)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('get template id error {}'.format(exc_value))
            return None

    def send_template_msg(self, open_id, template_id, data, url=None, mini_program=None):
        try:
            if open_id and template_id and data:
                self.wc_client.message.send_template(user_id=open_id, template_id=template_id, data=data, url=url,
                                                     mini_program=mini_program)
                return True
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('send template msg error {}'.format(exc_value))

    def get_js_signature(self, url):
        ticket = self.wc_client.jsapi.get_jsapi_ticket()
        nonce_str = random_string(16)
        time_stamp = int(time.time())
        signature = self.wc_client.jsapi.get_jsapi_signature(nonce_str, ticket, time_stamp, url=url)
        return dict(signature=signature, nonce_str=nonce_str, time_stamp=time_stamp, app_id=self.wc_client.appid)

    def get_menu(self):
        return self.wc_client.menu.get()

    def set_menu(self, data):
        button = json.loads(data)
        self.wc_client.menu.create(button)

    def material(self, media_type, offset, count):
        data = self.wc_client.material.batchget(media_type=media_type, offset=offset, count=count)
        return data

    def get_media(self, media_id, media_type, request=None):
        file_dir = os.path.join(settings.BASE_DIR, 'static/backend/temp/')
        if not os.path.isdir(os.path.join(settings.BASE_DIR, file_dir)):
            os.mkdir(os.path.join(settings.BASE_DIR, file_dir))

        if media_type == '1':
            media = self.wc_client.material.get(media_id=media_id)
            if not isinstance(media, list):
                return None
            return dict(media_id=media_id, content=dict(news_item=media))
        if media_type == '2':
            file_name = media_id + '.jpg'
            url = request.build_absolute_uri(settings.STATIC_URL + 'temp/' + file_name)
            if os.path.isfile(file_dir + file_name):
                return dict(media_id=media_id, url=url)
            else:
                media = self.wc_client.material.get(media_id=media_id)
                if not hasattr(media, 'content'):
                    return None
                with open(file_dir + file_name, 'w') as f:
                    f.write(media.content)
                return dict(media_id=media_id, url=url)
        if media_type == '3':
            file_name = media_id + '.mp3'
            url = request.build_absolute_uri(settings.STATIC_URL + 'temp/' + file_name)
            if os.path.isfile(file_dir + file_name):
                return dict(media_id=media_id, url=url)
            else:
                media = self.wc_client.material.get(media_id=media_id)
                if not hasattr(media, 'content'):
                    return None
                with open(file_dir + file_name, 'w') as f:
                    f.write(media.content)
                return dict(media_id=media_id, url=url)
        if media_type == '4':
            media = self.wc_client.material.get(media_id=media_id)
            if not isinstance(media, dict):
                return None
            return dict(name=media.get('title'), **media)
        return self.wc_client.material.get(media_id)

    def set_industry(self, industry_1, industry_2):
        try:
            self.wc_client.template.set_industry(industry_1, industry_2)
        except WeChatClientException as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('set mp industry fail for msg: {}'.format(exc_value))


class MpClientByOpen(MpClientBase):
    def __init__(self):
        self.host = 'http://open.liyunmall.com/'
        self.inst_token = 'kWvmOoV9'

    def get_user_info(self, open_id):
        resp = requests.post(url=self.host + 'api/mpclient/{}/user_info/'.format(self.inst_token),
                             data=dict(open_id=open_id))
        try:
            return resp.json()
        except ValueError:
            return None

    def send_text(self, open_id, msg):
        if open_id and msg:
            resp = requests.post(url=self.host + 'api/mpclient/{}/send_msg/'.format(self.inst_token),
                                 data=dict(open_id=open_id, msg=msg))
            if resp.status_code == 200:
                if not resp.json().get('success'):
                    logger.error('sent text error {}'.format(resp.json().get('msg')))
            else:
                logger.error('sent text error {}'.format(resp.status_code))

    def get_action_qr_code(self, key, val):
        resp = requests.get(url=self.host + 'api/mpclient/{}/get_action_qr_code/'.format(self.inst_token),
                            params=dict(key=key, val=val))
        try:
            return resp.json()
        except ValueError:
            return None

    def get_template_id(self, template_short_id):
        try:
            resp = requests.get(url=self.host + 'api/mpclient/{}/get_template_id/'.format(self.inst_token),
                                params=dict(template_short_id=template_short_id))
            return resp.json().get('template_id')
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('get template id error {}'.format(exc_value))
            return None

    def send_template_msg(self, open_id, template_id, data, url):
        try:
            if not open_id:
                return
            resp = requests.post(url=self.host + 'api/mpclient/{}/send_template/'.format(self.inst_token),
                                 json=dict(open_id=open_id, template_id=template_id, data=data, url=url))
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('send template msg error {}'.format(exc_value))

    def get_js_signature(self, url):
        resp = requests.get(url=self.host + 'api/jsapi/{}/signature/'.format(self.inst_token), params=dict(url=url))
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.error('sent text error {}'.format(resp.status_code))

    def get_menu(self):
        resp = requests.get(url=self.host + 'api/mpclient/{}/get_menu/'.format(self.inst_token))
        try:
            return json.loads(resp.content)
        except ValueError:
            return None

    def set_menu(self, data):
        try:
            resp = requests.post(url=self.host + 'api/mpclient/{}/set_menu/'.format(self.inst_token),
                                 json=dict(menu=data))
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('set menu msg error {}'.format(exc_value))

    def material(self, media_type, offset, count):
        try:
            resp = requests.get(url=self.host + 'api/mpclient/{}/material/'.format(self.inst_token),
                                params=dict(media_type=media_type, offset=offset, count=count))
            return json.loads(resp.content)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('get material id error {}'.format(exc_value))
            return None

    def get_media(self, media_id, media_type, request=None):
        try:
            resp = requests.get(url=self.host + 'api/mpclient/{}/get_media/'.format(self.inst_token),
                                params=dict(media_id=media_id, media_type=media_type))
            return resp.json()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error('get media error {}'.format(exc_value))
            return None

    def set_industry(self, industry_1, industry_2):
        return NotImplementedError


def get_mp_client():
    if use_open_platform:
        return MpClientByOpen()
    else:
        return MpClient()


class WXBizDataCrypt(object):
    def __init__(self, appId, sessionKey):
        self.appId = appId
        self.sessionKey = sessionKey

    # @pysnooper.snoop(log.debug)
    def decrypt(self, encryptedData, iv):
        # base64 decode
        sessionKey = base64.b64decode(self.sessionKey)
        log.info("sessionKey: %s" % sessionKey)
        log.info(encryptedData)
        encryptedData = base64.b64decode(encryptedData)
        log.info("len: %s" % len(encryptedData))

        iv = base64.b64decode(iv)

        cipher = AES.new(sessionKey, AES.MODE_CBC, iv)
        pt = cipher.decrypt(encryptedData)
        log.info("pt: %s" % pt)
        decrypted = json.loads(self._unpad(pt))
        log.info("decrypted: %s" % decrypted)

        if decrypted['watermark']['appid'] != self.appId:
            raise Exception('Invalid Buffer')

        return decrypted

    def _unpad(self, s):
        s1 = s[:-ord(s[len(s) - 1:])]
        log.info("s=s1: %s" % (s1 == s))
        return s1


class WxaTemplateMsgClient(object):
    def __init__(self, wxa_client):
        self._client = self.wechatwxaclient = wxa_client

    def get_or_add_order_success_template(self):
        """
        AT0009 订单支付成功通知

        :return:
            template_id
        """
        try:
            return MsgTemplate.objects.get(template_short_id='AT0009', type=MsgTemplate.TYPE_WEAPP).template_id
        except MsgTemplate.DoesNotExist:
            # 订单编号、商品名称、金额、订单状态、收货地址、取货方式
            template_id = self.wechatwxaclient.add_template('AT0009', [9, 10, 2, 8, 50, 101])
            MsgTemplate.objects.create(title='订单支付成功通知', template_group='order_success', template_short_id='AT0009',
                                       type=MsgTemplate.TYPE_WEAPP, template_id=template_id)
            return template_id

    def initial(self):
        """
        初始化模板库:
        查询并增加如下模板

        :return:
        """
        logger.debug('order_success_template' % self.get_or_add_order_success_template())

    def order_success(self, lp_openid, prepay_id, orderno, order_display, amount, status_display, express_address,
                      sender_way, page=None):
        """
        下单成功通知
        AT0009 订单支付成功通知
        模板：
            订单编号{{keyword1.DATA}}
            商品名称{{keyword2.DATA}}
            金额{{keyword3.DATA}}
            订单状态{{keyword4.DATA}}
            取货地址{{keyword5.DATA}}
            取货方式{{keyword6.DATA}}
        :return:
        """
        template_id = self.get_or_add_order_success_template()
        # log.debug('prepay_id: %s %s, template_id:%s %s' % (type(prepay_id), prepay_id, type(template_id), template_id))
        data = dict(keyword1=dict(value=orderno), keyword2=dict(value=order_display),
                    keyword3=dict(value=amount),
                    keyword4=dict(value=status_display),
                    keyword5=dict(
                        value=express_address),
                    keyword6=dict(value=sender_way))
        # log.debug('data: %s' % data)
        self._client.send_template_message(lp_openid, template_id,
                                           data, prepay_id,
                                           page)


class WeChatWxaClient(WeChatWxa):
    def __init__(self, appid, appsecret):
        global LP_SESSION_STORAGE
        if not LP_SESSION_STORAGE:
            LP_SESSION_STORAGE = RedisStorage(get_redis(), prefix='lp_client_session_%s_' % appid)
        super(WeChatWxaClient, self).__init__(WeChatClient(appid, appsecret, session=LP_SESSION_STORAGE))

    def get_replay(self, start, limit):
        self._client.auto_retry = False
        get_url = lambda: 'http://api.weixin.qq.com/wxa/business/getliveinfo?access_token=%s' % self.access_token
        return self._client.post(get_url(), json=dict(action="get_replay", start=start, limit=limit))

    def getliveinfo(self, start, limit):
        """
        获取直播列表
        :param start:
        :param limit:
        :return:
        {u'errcode': 0,
 u'errmsg': u'ok',
 u'live_replay': [],
 u'room_info': [{u'anchor_name': u'Jason Rowe',
   u'cover_img': u'http://mmbiz.qpic.cn/mmbiz_jpg/CgOVvyJU2HG2VAr9bGaZA02uOUOXIficJVlHXOkQ9rxGaQSGuZRA0SqN2Vs5OFocv3ibV5kAuCK6zlDFGHfnl2aA/0',
   u'end_time': 1584981480,
   u'goods': [],
   u'live_status': 102,
   u'name': u'\u9762\u819c\u7279\u5356\u4f1a\u5f00\u64ad\u5566\uff01\uff01\uff01',
   u'roomid': 5,
   u'share_img': u'http://mmbiz.qpic.cn/mmbiz_jpg/CgOVvyJU2HG2VAr9bGaZA02uOUOXIficJUUQVS0lh4jfM57okXhRVa4Umpuv71dOpEuibQFkImUdJx5fZkCSyiaTg/0',
   u'start_time': 1584979200},
  {u'anchor_name': u'\u8def\u9065',
   u'cover_img': u'http://mmbiz.qpic.cn/mmbiz_png/CgOVvyJU2HGvdHZmGeZ1GV42G2I37op85YT4ehCicrKNycz4uuGJIOxE5lV7KqFehw8tvicnwsREYxzLhU87iaUxQ/0',
   u'end_time': 1584525600,
   u'goods': [],
   u'live_status': 107,
   u'name': u'\u5b85\u7537\u517b\u6210\u8bb0',
   u'roomid': 4,
   u'share_img': u'http://mmbiz.qpic.cn/mmbiz_png/CgOVvyJU2HGvdHZmGeZ1GV42G2I37op85YT4ehCicrKNycz4uuGJIOxE5lV7KqFehw8tvicnwsREYxzLhU87iaUxQ/0',
   u'start_time': 1584504300},
  {u'anchor_name': u'\u8def\u9065',
   u'cover_img': u'http://mmbiz.qpic.cn/mmbiz_png/CgOVvyJU2HEicE8ibiaiaOBsf5wr9Lqick7nUwuerVTQTfhQhunNLugdknLRWkriaWRcTaiasxYnficZ6zS8AcVkI41etA/0',
   u'end_time': 1584159533,
   u'goods': [],
   u'live_status': 103,
   u'name': u'\u5b85\u7537\u517b\u6210\u8bb0',
   u'roomid': 3,
   u'share_img': u'http://mmbiz.qpic.cn/mmbiz_png/CgOVvyJU2HEicE8ibiaiaOBsf5wr9Lqick7nU34cDPIW8ic4WjoKL9vLjT1Z7atYtibpITzVMe6sVKpw8acgx3HficJaCw/0',
   u'start_time': 1584158346}],
 u'total': 3}
        """
        # disable auto_retry
        self._client.auto_retry = False

        get_url = lambda: 'https://api.weixin.qq.com/wxa/business/getliveinfo?access_token=%s' % self.access_token
        return self._client.post(get_url(), json=dict(start=start, limit=limit))

    def decrypt_phone(self, encryptedData, iv, session_key):
        """
        解密手机
        :param encryptedData:
        :param iv:
        :param session_key:
        :return:
        """
        # encryptedData = 'CiyLU1Aw2KjvrjMdj8YKliAjtP4gsMZMQmRzooG2xrDcvSnxIMXFufNstNGTyaGS9uT5geRa0W4oTOb1WT7fJlAC+oNPdbB+3hVbJSRgv+4lGOETKUQz6OYStslQ142dNCuabNPGBzlooOmB231qMM85d2/fV6ChevvXvQP8Hkue1poOFtnEtpyxVLW1zAo6/1Xx1COxFvrc2d7UL/lmHInNlxuacJXwu0fjpXfz/YqYzBIBzD6WUfTIF9GRHpOn/Hz7saL8xz+W//FRAUid1OksQaQx4CMs8LOddcQhULW4ucetDf96JcR3g0gfRK4PC7E/r7Z6xNrXd2UIeorGj5Ef7b1pJAYB6Y5anaHqZ9J6nKEBvB4DnNLIVWSgARns/8wR2SiRS7MNACwTyrGvt9ts8p12PKFdlqYTopNHR1Vf7XjfhQlVsAJdNiKdYmYVoKlaRv85IfVunYzO0IKXsyl7JCUjCpoG20f0a04COwfneQAGGwd5oa+T8yO5hzuyDb/XcxxmK01EpqOyuxINew=='
        # iv = 'r7BXXKkLb8qrSNn05n0qiA=='
        pc = WXBizDataCrypt(self.appid, session_key)
        return pc.decrypt(encryptedData, iv)

    def decrypt_encryptedData(self, encryptedData, iv, session_key):
        """
        解密
        :param encryptedData:
        :param iv:
        :param session_key:
        :return:
        """
        logger.info("encryptedData: %s, iv: %s, session_key: %s" % (encryptedData, iv, session_key))
        pc = WXBizDataCrypt(self.appid, session_key)

        return pc.decrypt(encryptedData, iv)

    def biz_get_wxa_code_unlimited(self, scene, page=None):
        """
        获取小程序码
        :param save_to:
        :return: buffer in type StringIO
        """
        resp = self.get_wxa_code_unlimited(scene, page=page)
        logger.debug('sc: %s, %s, %s' % (resp.status_code, scene, page))
        if resp.status_code == 200:
            from io import BytesIO
            buf = BytesIO()
            buf.write(resp.content)
            buf.flush()
            return buf

    def award_notice(self, lp_openid, title, session_name, amount, desc, page):
        # 小程序订阅消息
        """
        模板ID：Hc-oND-rTh8EUWGCnwniwAtdwmElts4fPaTYQjEvaPc
        模板编号：44049
        详细内容
        项目名称{{thing1.DATA}}
        场次名称{{thing2.DATA}}
        订单金额{{amount4.DATA}}
        备注{{thing5.DATA}}
        """
        template_id = 'Hc-oND-rTh8EUWGCnwniwAtdwmElts4fPaTYQjEvaPc'
        data = dict(thing1=dict(value='{}...'.format(title[0:12])),
                    thing2=dict(value='{}...'.format(session_name[0:12])),
                    amount4=dict(value=amount), thing5=dict(value=desc))
        self.send_subscribe_message(lp_openid, template_id, data, page=page)

    def show_start_notice(self, lp_openid, address, show_name, start_at, order_desc, page):
        """
        模板ID：5ueeapkeErHOOg-HIfqLJSIgnWAY5pbqtJ0QADIMXOY
        模板编号：2299
        详细内容
        项目名称{{thing1.DATA}}
        演出时间{{date2.DATA}}
        演出地点{{thing3.DATA}}
        订单详情{{thing4.DATA}}
        """
        template_id = '5ueeapkeErHOOg-HIfqLJSIgnWAY5pbqtJ0QADIMXOY'
        data = dict(thing1=dict(value=show_name), date2=dict(value=start_at), thing3=dict(value=address),
                    thing4=dict(value=order_desc))
        self.send_subscribe_message(lp_openid, template_id, data, page=page)

    def generate_scheme(self, path, query):
        url = 'https://api.weixin.qq.com/wxa/generatescheme?access_token=%s' % self.access_token
        data = {
            "jump_wxa":
                {
                    "path": path,
                    "query": query
                },
            "expire_type": 1,
            "expire_interval": 29
        }
        return self._client.post(url, json=data)

    def generate_urllink(self, path, query):
        url = 'https://api.weixin.qq.com/wxa/generate_urllink?access_token=%s' % self.access_token
        data = {
            "path": path,
            "query": query,
            # "is_expire":true,
            "expire_type": 1,
            "expire_interval": 30,
            "env_version": "trial",
            # "cloud_base":
            # {
            #     "env": "xxx",
            #     "domain": "xxx.xx",
            #     "path": "/jump-wxa.html",
            #     "query": "a=1&b=2"
            # }
        }
        return self._client.post(url, json=data)


_WXA_CLIENT = None


def get_wxa_client(configs=None):
    global _WXA_CLIENT
    if not _WXA_CLIENT:
        # appid, appsecret = configs or map(config, ['open_lp_app_id', 'open_lp_app_secret'])
        sy = SystemWxMP.get()
        if sy:
            appid, appsecret = sy.app_id, sy.app_secret
        else:
            appid, appsecret = map(config, ['open_lp_app_id', 'open_lp_app_secret'])
        _WXA_CLIENT = WeChatWxaClient(appid, appsecret)
    return _WXA_CLIENT


_WXA_TEMPLATE_CLIENT = None


def get_wxa_template_client():
    """
    小程序模板消息客户端
    :return:
    """
    global _WXA_TEMPLATE_CLIENT
    if not _WXA_TEMPLATE_CLIENT:
        _WXA_TEMPLATE_CLIENT = WxaTemplateMsgClient(get_wxa_client())
    return _WXA_TEMPLATE_CLIENT


# LP_SHOP_SESSION_STORAGE = None
# _WXA_SHOP_CLIENT = dict()
#
#
# class WeChatWxaShopClient(WeChatWxa):
#     def __init__(self, appid, appsecret):
#         global LP_SHOP_SESSION_STORAGE
#         if not LP_SHOP_SESSION_STORAGE:
#             LP_SHOP_SESSION_STORAGE = RedisStorage(get_redis(), prefix='lp_shop_client_session_%s_' % appid)
#         super(WeChatWxaShopClient, self).__init__(WeChatClient(appid, appsecret, session=LP_SHOP_SESSION_STORAGE))
#
#     def get_cat(self):
#         # 获取商品类目
#         """
#         https://developers.weixin.qq.com/miniprogram/dev/platform-capabilities/
#         business-capabilities/ministore/minishopopencomponent2/API/cat/get_children_cateogry.html
#         若该类目资质必填，则新增商品前，必须先通过该类目资质申请接口进行资质申请;
#         若该类目资质不需要，则该类目自动拥有，无需申请，如依然调用，会报错1050011；
#         若该商品资质必填，则新增商品时，带上商品资质字段。 接入类目审核回调，才可获取审核结果。
#         """
#         url = '{}shop/cat/get?access_token={}'.format(self.API_BASE_URL, self.access_token)
#         ret = self._client.get(url)
#         third_cat_list = ret['third_cat_list']
#         return third_cat_list
#
#     def img_upload(self, file_path):
#         # Content-Type: multipart/form-data， 图片大小限制2MB
#         url = '{}shop/img/upload?access_token={}'.format(self.API_BASE_URL, self.access_token)
#         try:
#             headers = {'Content-Type': 'multipart/form-data'}
#             params = dict(resp_type=0, upload_type=0)
#             resp = requests.post(url, files={'media': open(file_path, 'rb')}, json=params, headers=headers)
#             if resp.status_code == 200:
#                 ret = resp.json()
#                 log.error(ret)
#                 if ret['errcode'] == 0:
#                     return True, ret['img_info']
#         except Exception as e:
#             log.error(e)
#             return False, ''
#
#     def audit_category(self, license_url: str, level1: int, level2: int, level3: int, certificate: list):
#         # 使用到的图片的地方，可以使用url或media_id(通过上传图片接口换取)
#         url = '{}shop/audit/audit_category?access_token={}'.format(self.API_BASE_URL, self.access_token)
#         params = {
#             "audit_req":
#                 {
#                     # 营业执照
#                     "license": [license_url],
#                     "category_info":
#                         {
#                             "level1": level1,
#                             "level2": level2,
#                             "level3": level3,
#                             "certificate": certificate  # 资质材料
#                         },
#                     "scene_group_list": [1]
#                 }
#         }
#         ret = self._client.post(url, json=params)
#         third_cat_list = ret['third_cat_list']
#         return third_cat_list
#
#
# def get_wxa_shop_client(appid=None, appsecret=None):
#     """
#     小程序视频号客户端
#     :return:
#     """
#     global _WXA_SHOP_CLIENT
#     if not appid:
#         sy = SystemWxShop.get()
#         if sy:
#             appid, appsecret = sy.app_id, sy.app_secret
#     if not appid:
#         raise ValueError('先配置微信视频号小店')
#     if not _WXA_SHOP_CLIENT.get(appid):
#         _WXA_SHOP_CLIENT[appid] = WeChatWxaShopClient(appid, appsecret)
#     return _WXA_SHOP_CLIENT[appid]
