# coding: utf-8
import logging
import random
import time
import os
from common.config import get_config
from restframework_ext.exceptions import CustomAPIException
from caches import with_redis
from captcha.image import ImageCaptcha
import hashids

logger = logging.getLogger(__name__)
from common.utils import random_digits, MediaUtil

KEY_EXPIRE = 1800
PKEY_EXPIRE = 1800000


def check_key_too_fast(key, passed_pttl=1000, pexpiration=PKEY_EXPIRE):
    """
    检查key, 在总过期时间:pexpiration下, 是否过去了:passed_pttl时间,避免太频繁的操作.
    如果key不存在时,是正常情况。
    如果key没有设置过期的时候,是异常情况.
    调用这个方法的场景是:
    我需要写入某个key,要求同个key不能写入过于频繁,可以重复写入的场景, 比如1s钟一次, 两次间隔低于1s是要拒绝的, 超过1s，可以覆盖写入.
    :param key:
    :param elapse_pttl:
    :param pexpiration:
    :return:
        要么抛异常,要么通过
    """
    with with_redis() as redis:
        pttl = redis.pttl(key)
        if pttl == -1:
            logger.error('{} has not expiration, can not check expiration!!!'.format(key))
            raise CustomAPIException('unkonwn key')
        elif pttl == -2:
            pass
        if pttl >= 0 and (pexpiration - pttl) < passed_pttl:
            raise CustomAPIException('request_too_fast')
        else:
            pass


def check_key_expired(key, elapse_pttl=1000, pexpiration=PKEY_EXPIRE):
    """
    检查key, 在总过期时间:pexpiration下, 是否还剩余:elapse_pttl时间
    :param key:
    :param elapse_pttl:
    :param pexpiration:
    :return:
    要么抛异常,要么通过
    """
    with with_redis() as redis:
        pttl = redis.pttl(key)
        if pttl == -1:
            logger.error('{} has not expiration, can not check expiration!!!'.format(key))
            raise CustomAPIException('unkonwn key')
        elif pttl == -2:
            raise CustomAPIException('sms_ucap_expired_or_not_found')
        elif pttl >= 0 and (pexpiration - pttl) < elapse_pttl:
            raise CustomAPIException('sms_ucap_expired_or_not_found')
        else:
            pass


def get_cap_key(prefix, reqid, mobile):
    """
    获取图片验证码的
    :param rand:
    :return:
    """
    return '{}:cap:{}:{}'.format(prefix, reqid, mobile)


def get_send_sms_code_key(prefix, reqid, mobile, imgrand):
    """
    短信的key -> 验证码
    :param reqid:
    :param mobile:
    :param imgrand:
    :return:
    """
    return '{}:sms:1:{}:{}:{}'.format(prefix, reqid, mobile, imgrand)


def get_send_sms_code_key_simple(reqid, mobile):
    """
    短信的key -> 验证码
    :param reqid:
    :param mobile:
    :param imgrand:
    :return:
    """
    return '{}:sms:0:{}:{}'.format(key_prefix(), reqid, mobile)


def key_prefix():
    """
    app key prefix to avoid conflict with other
    :return:
    """
    conf = get_config()
    return conf.get('redis').get('prefix')


def get_reqid_key(reqid):
    """
    获取reqid的key
    :param reqid:
    :return:
    """
    return '{}:ucap:{}'.format(key_prefix(), reqid)


def smscode_response(imgrand, reqid, mobile):
    """
    sms:<reqid>:<mobile>:<imgrand>  -> smscode

    验证短信验证码时, 使用key来验证: sms:<reqid>:<mobile>:<imgrand>
    :param data:
    :return:
    """
    conf = get_config().get('open_captcha')
    oc = conf.get('code')

    from qcloud.sms import get_sms
    data = dict()
    data['mobile'] = mobile
    data['timeout'] = '5'
    data['code'] = code = random_digits(6)
    if oc == 1:
        if not imgrand:
            raise CustomAPIException('bad_request')
        with with_redis() as redis:
            prefix = conf.get('redis').get('prefix')
            cap_key = get_cap_key(prefix=prefix, reqid=reqid, mobile=mobile)
            # 检查图片验证码
            expect = redis.get(cap_key)
            if not expect:
                raise CustomAPIException('图片验证码过期')
            if expect == imgrand:
                key = get_send_sms_code_key(reqid, mobile, imgrand)
                if redis.setnx(key, code):
                    redis.expire(key, KEY_EXPIRE)
                    inst = get_sms()
                    resp = inst.smsvrcode(data)
                    if resp:
                        return True
                    else:
                        raise CustomAPIException('sms_upstream_error', code=500)
                else:
                    raise CustomAPIException('request_too_fast')
            else:
                # 图片验证码错误
                raise CustomAPIException('err_captcha')
    elif oc == 0:
        key = get_reqid_key(reqid)
        with with_redis() as redis:
            if 1 == redis.delete(key):
                key = get_send_sms_code_key_simple(reqid, mobile)
                if redis.setnx(key, code):
                    redis.expire(key, KEY_EXPIRE)
                    inst = get_sms()
                    resp = inst.smsvrcode(data)
                    if resp:
                        return True
                    else:
                        raise CustomAPIException('sms_upstream_error', code=500)
                else:
                    raise CustomAPIException('request_too_fast')
            else:
                raise CustomAPIException('请退出重新刷新页面')
    else:
        raise CustomAPIException('sys_init_error')


def usecap_response(sk):
    """
    ucap:<reqid> -> 1
    :param sk:
    :return:
    """
    if sk not in get_config().get('appids'):
        raise CustomAPIException('appids invaid')
    with with_redis() as redis:
        reqid = random_digits(6)
        key = get_reqid_key(reqid)
        if redis.setnx(key, 1):
            redis.expire(key, KEY_EXPIRE)
            data = dict(reqid=reqid)
            conf = get_config().get('open_captcha')
            data['code'] = conf.get('code')
            return data
        else:
            raise CustomAPIException('request_too_fast')


def validate_cap_request(reqid, mobile):
    """
    1.检查reqid是否过期
    2.检查请求是否过于频繁
    :return:
    """
    check_key_expired(get_reqid_key(reqid))
    check_key_too_fast(get_cap_key(reqid, mobile), 1000)


SLUG_SALT = 'HASdkasdkjasd9kasdkla!()sdaskdsa812839asd9128'


def auto_slug(salt=None):
    """
    length range [34, 38]
    :return:
    """

    ri = random.randint(0, 999)
    ts = list(str(int(1000000 * time.time()))) + list(str(ri))
    int_seqs = [int(e) for e in ts]
    salt = salt or SLUG_SALT
    return hashids.Hashids(salt=salt, min_length=8).encode(*int_seqs)


def captcha_response(reqid, mobile):
    """
    cap:<reqid>:mobile -> imgrand
    用户输入错误图片验证码的时候重新输入,所以这个不能锁定key.
    比较好的办法是,应该还有一个辅助key或者是存一个hash,记录时间,两次间隔不能低于1~2秒, 还一个做法：
    检查key的ttl，看是否间隔了1~2秒
    :param args:
    :param kwargs:
    :return:
    """
    validate_cap_request(reqid, mobile)
    cap = ImageCaptcha(width=260, height=120)
    from random import sample
    import string
    rand = ''.join(sample(string.digits, 4))
    filename = '{}.png'.format(auto_slug())
    media_root = MediaUtil.media_root
    dir = os.path.join(media_root, 'cap')
    if not os.path.isdir(dir):
        os.mkdir(dir)
    cap.write(rand, os.path.join(media_root, 'cap', filename))
    with with_redis() as redis:
        key = get_cap_key(reqid, mobile)
        redis.set(key, rand)
        redis.expire(key, KEY_EXPIRE)
        return dict(url=MediaUtil.get_media_url('cap/{}'.format(filename)))
