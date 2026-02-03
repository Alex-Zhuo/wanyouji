# coding: utf-8

import json, requests
from urllib.error import HTTPError

from caches import with_redis
from mall.mall_conf import MallSettings
import logging

log = logging.getLogger(__name__)
host = 'https://ali-deliver.showapi.com'
path = '/showapi_expInfo'
method = 'GET'
appcode = MallSettings.express_api_appcode

ex_vendor_url = 'http://wuliu.market.alicloudapi.com/kdi'
ex_vendor_subscribe_url = 'http://expfeeds.market.alicloudapi.com/expresspush'


def query_express(express_code, express_no):
    try:
        key = '%s_%s' % (express_no, express_code)
        with with_redis() as redis:
            # ok = redis.setnx('%s_%s'%(express_no, express_code))
            data = redis.hgetall(key)
            if not data:
                log.debug('load from remote: %s' % key)
                querys = 'type={}&no={}'.format(express_code, express_no)
                url = ex_vendor_url + '?%s' % querys
                log.debug('request: %s' % url)
                resp = requests.get(url, headers={'Authorization': 'APPCODE ' + appcode}, timeout=3)
                if resp.status_code == 200:
                    jcont = resp.json()
                    if jcont.get('status') == '0':
                        if jcont.get('result').get('issign') == '1':
                            # 已签收,结果保存30天
                            redis.hmset(key, dict(issign=1, data=resp.content))
                            redis.expire(key, 30 * 24 * 3600)
                        else:
                            # 在途的，保存2小时
                            # l = jcont.get('result').get('list')
                            timeout = 6 * 3600
                            # if l:
                            #     ts = time.mktime(datetime.strptime(l[0]['time'], '%Y-%m-%d %H:%M:%S').timetuple())
                            #     now = time.time()
                            #     # 至少缓存半小时，至多2小时
                            #     timeout = min(max(now - ts, 1800), 2 * 3600)
                            redis.hmset(key, dict(issign=0, data=resp.content, ts=timeout))
                            redis.expire(key, int(timeout))
                    else:
                        log.error('error express: %s, %s' % (key, resp.content))
                        redis.hmset(key, dict(error=resp.content))
                        redis.expire(key, 12 * 3600)
                return True, resp.json()
            else:
                # log.debug('load from cache: %s' % data)
                # data = json.loads(data)
                return True, (json.loads(data.get('data')) if data.get('data') else json.loads(data.get('error')))
    except HTTPError as e:
        return False, dict(msg=u'请求快递服务异常')
    except ValueError:
        return False, dict(msg=u'请求快递服务异常')
    except (requests.Timeout, requests.ConnectTimeout):
        return False, dict(msg=u'请求快递服务超时')


def express_subscribe(express_code, express_no, url):
    """
    订阅快递推送
    :param express_code:
    :param express_no:
    :param url:
    :return:
    订阅接口正常返回内容
    {
	"orderid": "15596148193983087919",
	"status": true, # 错误返回false
        "code":"300", # 返回错误码，对应下表
	"no": "JDVE00023862621",
	"type": "JD",
	"url": "http:\/\/127.0.0.1\/test.php",
	"message": "请求成功，开始推送"
}

错误码	错误信息	描述
101	快递单号错误	快递单号错误
102	快递单号或快递公司代码不能为空	快递单号或快递公司代码不能为空
103	快递公司代码错误[请参考产品详情]	快递公司代码错误[请参考产品详情]
104	回调url地址错误，请传递正确url地址	回调url地址错误，请传递正确url地址
201	url地址访问不通	url地址访问不通
300	请求成功，开始推送	请求成功，开始推送
301	重复提交推送请求，已开始推送	重复提交推送请求，已开始推送
    """
    try:
        querys = 'type={}&no={}&url={}'.format(express_code, express_no, url)
        url = ex_vendor_subscribe_url + '?%s' % querys
        resp = requests.get(url, headers={'Authorization': 'APPCODE ' + appcode})
        log.debug('%s, %s' % (resp.status_code, resp.content))
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') and str(data.get('code')) in ('300', '301'):
                return True, None
            else:
                return False, data.get('message')
        else:
            return False, None

    except HTTPError as e:
        return False, u'网络错误001'
    except ValueError:
        return False, u'网络错误002'


def query_express_dep(express_code, express_no):
    try:
        # querys = 'com={}&nu={}'.format(express_code, express_no)
        # url = host + path + '?' + querys
        # request = urllib2.Request(url)
        # request.add_header('Authorization', 'APPCODE ' + appcode)
        # ctx = ssl.create_default_context()
        # ctx.check_hostname = False
        # ctx.verify_mode = ssl.CERT_NONE
        # response = urllib2.urlopen(request, context=ctx)
        # content = response.read()
        # if content:
        #     return json.loads(content)
        # return None
        querys = 'com={}&nu={}'.format(express_code, express_no)
        url = host + path + '?' + querys
        resp = requests.get(url, headers={'Authorization': 'APPCODE ' + appcode})
        return resp.json()
    except HTTPError as e:
        return None
    except ValueError:
        return None
