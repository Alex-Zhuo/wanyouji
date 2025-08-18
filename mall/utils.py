# coding: utf-8
import hashlib
import os
import string

from django.utils import timezone
from random import sample
import hashids
from mall.mall_conf import user_share_code_salt, qrcode_filename_salt


def randomstrwithdatetime(tail_length=6):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return '%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def random_theater_card_no(tail_length=6):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'No%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def random_theater_order_no(tail_length=6):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'TC%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def randomstrwithdatetime_card(tail_length=6):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'C%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def randomstrwithdatetime_so(tail_length=6):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'SO%s%s' % (now.strftime('%Y%m%d%H%M%S'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def gen_express_no():
    return randomstrwithdatetime(8)


def str_2_hex(s):
    return "".join(['%0X' % ord(b) for b in s])


def gen_user_share_code(user_id, salt=user_share_code_salt):
    return '{}{}'.format(hashids.Hashids(salt=salt, min_length=8).encode(user_id), user_id)


def gen_user_u_id(user_id, salt=user_share_code_salt):
    return '{}'.format(hashids.Hashids(salt=salt, min_length=10).encode(user_id))


def uploads_dir_and_relative_url():
    from django.conf import settings
    return settings.MEDIA_ROOT, settings.MEDIA_URL


def get_media_meta(relative_path):
    """

    :param relative_path: relative directory or path
    :return:
    """
    from django.conf import settings
    rel_url = settings.MEDIA_URL + relative_path
    return os.path.join(settings.MEDIA_ROOT, relative_path), rel_url


def qrcode_dir():
    """
    二维码存放的文件目录、相对url(相对于media_root，不包含文件名)
    :return:
    """
    from django.conf import settings
    rel_url = settings.MEDIA_URL + '/'.join(['mall', 'qrcodes'])
    return os.path.join(settings.MEDIA_ROOT, 'mall', 'qrcodes'), rel_url


def qrcode_dir_pro():
    """
    在qrcode_dir创建目录
    :return:
    """
    dir, rel_url = qrcode_dir()
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir, rel_url


def qrcode_tk(name: str = None):
    """
    二维码存放的文件目录、相对url(相对于media_root，不包含文件名)
    :return:
    """
    from django.conf import settings
    if not name:
        name = 'qrcodes'
    rel_url = settings.MEDIA_URL + '/'.join(['ticket', name])
    return os.path.join(settings.MEDIA_ROOT, 'ticket', name), rel_url, '/'.join(['ticket', name])


def qrcode_dir_tk(name: str = None):
    """
    在qrcode_dir创建目录
    :return:
    """
    dir, rel_url, img_dir = qrcode_tk(name)
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir, rel_url, img_dir


def cert_dir():
    return get_media_meta('agents/cert')


def obfuscate(nonce, nonce_visible=True):
    data = ''.join([qrcode_filename_salt, nonce])
    return hashlib.md5(data.encode('utf-8')).hexdigest()


def random_string(length=16):
    rule = string.ascii_letters + string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


def get_mall_config():
    pass


def save_file(path, data):
    with open(path, 'w') as f:
        f.write(data)


def protocol_sign_dir():
    from django.conf import settings
    rel_url = settings.MEDIA_URL + '/'.join(['protocol', 'sign'])
    return os.path.join(settings.MEDIA_ROOT, 'protocol', 'sign'), rel_url


def qrcode_dir_zcao_o():
    """
    二维码存放的文件目录、相对url(相对于media_root，不包含文件名)
    :return:
    """
    from django.conf import settings
    rel_url = settings.MEDIA_URL + '/'.join(['zcao', 'qrcodes'])
    return os.path.join(settings.MEDIA_ROOT, 'zcao', 'qrcodes'), rel_url


def qrcode_dir_zcao():
    """
    在qrcode_dir创建目录
    :return:
    """
    dir, rel_url = qrcode_dir_zcao_o()
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir, rel_url
