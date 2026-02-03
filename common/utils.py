# coding: utf-8
import collections
import string
import time
from decimal import Decimal
from random import sample
import hashlib
import redis
import json
import six
from django.db import connections
from common.config import get_config, IMAGE_FIELD_PREFIX
import os
from django.conf import settings
import qrcode
from PIL import Image


class IterableHook(collections.Iterable):
    def __init__(self, iter, hook=None, offset=0, filter=None):
        self._iter = iter
        self._hook = hook if hook and callable(hook) else lambda i: i
        self._offset = offset
        self._current_index = -1
        self._filter = filter or (lambda e: True)

    @property
    def current_index(self):
        return self._current_index

    def __iter__(self):
        for i in self._iter:
            if i < self._offset:
                continue
            self._current_index += 1
            e = self._hook(i)
            if self._filter(e):
                yield e

    class EmptyError(RuntimeError):
        pass


class AddSmsQueue(object):
    __instance = None
    __pool = None

    msg_dict = {
        'direct_award': u'您获得了一条金额为{}的直推奖励，详情可登录个人中心查看',
        'planc_award': u'您获得了一条金额为{}的绩效奖励，详情可登录个人中心查看'
    }

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super(AddSmsQueue, cls).__new__(cls, *args, **kwargs)
        return cls.__instance

    def __init__(self):
        if self.__pool is None:
            self.__pool = redis.ConnectionPool(host='127.0.0.1', port=6379)

    def add_new(self, phone, msg_type, amount):
        r = redis.StrictRedis(connection_pool=self.__pool)
        msg = self.msg_dict.get(msg_type).format(amount)
        r.lpush('sms_queue', json.dumps((phone, msg)))


def close_old_connections():
    for conn in connections.all():
        conn.close_if_unusable_or_obsolete()


def run_ensure_connection(callback):
    """
    在异步方法调用中,确保函数使用的连接不会过期
    :param callback:
    :return:
    """

    def run():
        close_old_connections()
        return callback()

    return run


def random_str(length=16):
    rule = string.ascii_letters + string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


def gen_slug(length=16):
    rule = string.ascii_lowercase + string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


def quantize_half_up_cxt():
    import decimal
    ct = decimal.DefaultContext.copy()
    # 四舍五入
    ct.rounding = decimal.ROUND_HALF_UP
    return ct


def quantize(d, decimal_places=1):
    """
    四舍五入
    :param d:
    :param decimal_places:
    :return:
    """
    assert isinstance(decimal_places, int) and decimal_places > 0
    s = str(1.0 / (10 ** decimal_places))
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(s)
    return d.quantize(q, rounding=ROUND_HALF_UP)


def decimal_pretty(value):
    """
    如果1.0, 则转化为1, 用于字符串显示
    :param value:
    :return:
    """
    if value is not None:
        i = int(value)
        if Decimal(i) == value:
            return Decimal(i)
        else:
            return value


class AsciiIterableDict(collections.Iterable):

    def __init__(self, dict_data):
        assert isinstance(dict_data, dict)
        self._dict_data = dict_data
        self._keys = dict_data.keys()
        self._keys.sort()

    def __iter__(self):
        for k in self._keys:
            yield k, self._dict_data[k]


def ascii_order_dict(source):
    """
    排序字典
    :param source:
    :return:
    """
    d = collections.OrderedDict()
    for k, v in AsciiIterableDict(source):
        d[k] = v
    return d


def export_model_2_excel_in_admin(iterable, name=None, headers=None, iter_parser=None):
    """
    export model lines into excel, by admin
    :param iterable: a iterable such as queryset or list
    :param headers: the table header
    :param iter_parser: if element of iterable is object, than need a iter_parse to parse it to a list
    :return:
    """
    from django.http import HttpResponse
    response = HttpResponse(content_type='application/vnd.ms-excel')
    if iter_parser:
        assert callable(iter_parser)

    response['Content-Disposition'] = 'attachment; filename="{}.xls"'.format(name or '导出')

    def _write_row_by_xlwt(ws, cells, row_index):
        """
        :param ws:
        :param cells: cell values
        :param row_index: 1-relative row index
        :return:
        """
        for col, cell in enumerate(cells, 0):
            ws.write(row_index - 1, col, cell)

    import xlwt
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('sheet1')
    row_index = 1
    if headers:
        _write_row_by_xlwt(ws, headers, row_index)
        row_index += 1
    if iter_parser:
        for line in iterable:
            _write_row_by_xlwt(ws, iter_parser(line), row_index)
            row_index += 1
    else:
        for line in iterable:
            _write_row_by_xlwt(ws, line, row_index)
            row_index += 1
    wb.save(response)
    return response


def now_ts(milliseconds=False):
    """
    当前时间戳
    :param milliseconds:
    :return:
    """
    return int(time.time()) if not milliseconds else int(time.time() * 1000)


class Version(object):
    def __init__(self, version_str):
        """
        x.yy.zzz
        y不能超过2位
        z不能超过3位
        :param version_str:
        """
        self._version = version_str
        self._a, self._b, self._c = [int(x) for x in version_str.split('.')[:3]]
        self._weight = self._a * 100000 + self._b * 1000 + self._c

    # def __cmp__(self, other):
    #     if isinstance(other, self.__class__):
    #         return cmp(self._weight, other._weight)
    #     else:
    #         return 1

    def __str__(self):
        return str(self._weight)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self._weight == other._weight


def is_local_ip(ip):
    """
    是否为本地地址
    :param ip:
    :return:
    """
    return ip in ('127.0.0.1', '::1')


def is_white_ip(ip):
    """
    是否为白名单
    :param ip:
    :return:
    """
    from common.config import get_config
    ip_wl = get_config()['api_white_ip']
    return ip in ip_wl


def model_check(model, data):
    return dict([(k, data[k]) for k in data.keys() if k in [x.name for x in model._meta.fields]])


def to_text(value, encoding='utf-8'):
    """Convert value to unicode, default encoding is utf-8

    :param value: Value to be converted
    :param encoding: Desired encoding
    """
    if not value:
        return ''
    if isinstance(value, six.text_type):
        return value
    if isinstance(value, six.binary_type):
        return value.decode(encoding)
    return six.text_type(value)


def to_binary(value, encoding='utf-8'):
    """Convert value to binary string, default encoding is utf-8

    :param value: Value to be converted
    :param encoding: Desired encoding
    """
    if not value:
        return b''
    if isinstance(value, six.binary_type):
        return value
    if isinstance(value, six.text_type):
        return value.encode(encoding)
    return to_text(value).encode(encoding)


def format_url(params):
    data = [to_binary('{0}={1}'.format(k, params[k])) for k in sorted(params) if params[k]]
    return b"&".join(data)


def calculate_signature(params):
    url = format_url(params)
    return to_text(hashlib.md5(url).hexdigest().upper())


def random_digits(length=16):
    rule = string.digits
    rand_list = sample(rule, length)
    return ''.join(rand_list)


class MediaUtil:

    def __init__(self):
        self._media_url = get_config().get('MEDIA_URL')

    @property
    def media_url(self):
        if not self._media_url:
            raise ValueError('media url is not config to use')
        return self._media_url

    @property
    def media_root(self):
        return get_config().get('MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))

    def get_media_url(self, rel_path):
        """
        根据相对路径获取绝对路径
        :param rel_path:
        :return:
        """
        return '{}{}'.format(self.media_url, rel_path)


MediaUtil = MediaUtil()


# 检验是否含有中文字符
def is_contains_chinese(strs):
    for _char in strs:
        if u'\u4e00' <= _char <= u'\u9fa5':
            return True
        elif _char == " ":
            return True
    return False


def qrcode_dir(app):
    from django.conf import settings
    rel_url = settings.MEDIA_URL + '/'.join([app, 'qrcodes'])
    return os.path.join(settings.MEDIA_ROOT, app, 'qrcodes'), rel_url


def obfuscate(nonce):
    qrcode_filename_salt = 'xsa!@#!@#xxsfdsfdskalsdjl'
    data = ''.join([qrcode_filename_salt, nonce])
    return hashlib.md5(data.encode('utf-8')).hexdigest()


def _resolve_icon_box(size, default_size=120):
    w, h = size
    left, upper = (w - default_size) / 2, (h - default_size) / 2
    right, lower = left + default_size, upper + default_size
    return left, upper, right, lower


def _correct(icon, icon_box):
    width, height = icon_box[2] - icon_box[0], icon_box[3] - icon_box[1]
    if icon.size != (width, height):
        return icon.resize((width, height), Image.ANTIALIAS)
    return icon


def merge(bg, icon, icon_box):
    # transparent_bg = Image.new('RGBA', bg.size, (255,) * 4)
    bg, icon = bg.convert('RGBA'), icon.convert('RGBA')
    bg.paste(icon, icon_box, icon)
    # transparent_bg.paste(bg, (0, 0))
    # transparent_bg.paste(icon, icon_box, mask=icon)
    return bg


def generate(url, size, save_path=None, icon=None, icon_box=None):
    """
    generate qrcode for url. if icon given, then paste it to qrcode, if icon_position not given, will paste to
    center.
    :param save_path: the save path to save image file
    :param url: the url str
    :param size: 2-tuple in pixel for (width, height)
    :param icon: the icon source, which is a file path
    :param icon_box: a 4-tuple (left, top, right, lower), if not given will be set center, and set width, heigh to 50, 50
    :return:
        True: succeed
        False: failed
    """
    if size[0] < 330:
        version = 1
    else:
        version = (size[0] - 330) / 40 + 1
    qr = qrcode.QRCode(version=version, error_correction=qrcode.ERROR_CORRECT_H, border=0)
    qr.add_data(url)
    qr.make()
    img = qr.make_image()
    if img.size[0] > size[0]:
        img.thumbnail(size)
    elif img.size[0] < size[0]:
        img = img.resize(size)

    if icon:
        icon_img = Image.open(icon)
        icon_box = icon_box or _resolve_icon_box(img.size)
        icon_img = _correct(icon_img, icon_box)
        img = merge(img, icon_img, icon_box)
    if not save_path:
        return img
    else:
        img.save(save_path)
        img.close()


def get_timestamp(date):
    import time
    return int(time.mktime(date.timetuple()) * 1000)


def check_tiktok_version(request):
    from common.config import get_config
    config = get_config()
    if request.META.get('HTTP_VERSION') == config['tiktok_v']:
        return True
    return False


def change_layer_time_to_datetime(dt: str):
    from datetime import datetime
    time_list = dt.split(' ')
    start_at_time = '{} {} {} {} {}'.format(time_list[0], time_list[1], time_list[2], time_list[3],
                                            time_list[4])
    return datetime.strptime(start_at_time, '%a %b %d %Y %H:%M:%S')


def common_return() -> dict:
    return dict(code=0, msg='')


def split_numbers_and_text(input_string):
    import re
    return re.split(r'(\d+)', input_string)


def get_jwt(key, data):
    import jwt
    data['timestamp'] = int(time.time())
    token = jwt.encode(data, key)
    # jwt.decode(token,key,algorithms='HS256')
    return token


def s_name(name):
    if len(name) > 2:
        return '{}*{}'.format(name[:1], name[-1:])
    return '{}*'.format(name[:1])


def s_mobile(mobile):
    return '{}***{}'.format(mobile[:3], mobile[-4:])


def show_content(content):
    return '{}***{}'.format(content[:3], content[-4:])


def s_id_card(id_card):
    return '{}***{}'.format(id_card[:3], id_card[-4:])


def md5_content(content: str):
    from hashlib import md5
    md = md5()
    md.update(bytes(content, 'utf-8'))
    return md.hexdigest()


def random_new_digits(length: int, population: str = string.digits) -> str:
    import random
    bl = len(population)
    if bl < length:
        population = population * int(length / bl) + population[:length % bl]
    return ''.join(random.sample(population, length))


def hash_ids(num: int, min_length=32, ap_salt=None):
    import hashids
    salt = 'kask12ijsaasgjkuynghal98jghhskjgtu7421547dklsa129dasjjjatrutiiktghfaggjlru89875tihjgjan'
    if ap_salt:
        salt = salt + ap_salt
    h = hashids.Hashids(salt=salt, min_length=min_length)
    return h.encode(num)


def sha256_str(data: str):
    from hashlib import sha256
    sha256_hash = sha256()
    sha256_hash.update(data.encode('utf-8'))
    return sha256_hash.hexdigest()


def group_by_str(s: str, num: int):
    import itertools
    # num 每个组的字符数量
    # 使用itertools.zip_longest以两个两个字符为单位进行分组
    grouped = itertools.zip_longest(*[iter(s)] * num)
    # 使用列表推导式来转换成列表，并且将None替换为空字符串
    # return [''.join(filter(None, group)) for group in grouped]
    return grouped


def random_letter(length=8):
    rule = string.ascii_lowercase
    rand_list = sample(rule, length)
    return ''.join(rand_list)


def get_common_uuid(pk: int, prefix: str = None):
    import random
    ss = str(random.randint(100, 999))
    ln = 8 if pk < 100000000 else len(str(pk))
    i = ln + 3
    code = int(ss.ljust(i, '0')) + pk
    ret = str(code) + random_letter(2)
    return prefix + ret if prefix else ret


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def secure_update(obj, ignore_none=True, **kwargs):
    """
    安全更新对象, 如果值不同才更新
    :param ignore_none: 是否忽略空值
    :param obj:
    :param kwargs:
    :return:
    """
    update_fields = []
    for k, v in kwargs.items():
        if ignore_none and (v is None):
            continue
        if getattr(obj, k, None) != v:
            setattr(obj, k, v)
            update_fields.append(k)
    if update_fields:
        # log.debug("update_fields: %s" % update_fields)
        obj.save(update_fields=update_fields)
    return update_fields


def get_no():
    import uuid
    return uuid.uuid4().hex


def get_short_no():
    import secrets
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(16))


def save_url_img(img_url: str, logo_mobile_dir: str):
    from common.qrutils import open_image_by_url
    logo_mobile = open_image_by_url(img_url)
    file_path = os.path.join(settings.MEDIA_ROOT, logo_mobile_dir)
    if not os.path.isdir(file_path):
        os.makedirs(file_path)
    file_name = f'{sha256_str(img_url)}.png'
    img = f'{file_path}/{file_name}'
    logo_mobile_path = f'{logo_mobile_dir}/{file_name}'
    logo_mobile.save(img)
    return logo_mobile_path


def qrcode_cy(filepath_name: str):
    """
    二维码存放的文件目录、相对url(相对于media_root，不包含文件名)
    :return:
    """
    from django.conf import settings
    rel_url = settings.MEDIA_URL + '/'.join(['cy_ticket', filepath_name])
    return os.path.join(settings.MEDIA_ROOT, 'cy_ticket', filepath_name), rel_url, '/'.join(
        ['cy_ticket', filepath_name])


def qrcode_dir_cy(filepath_name: str):
    """
    在qrcode_dir创建目录
    :return:
    """
    dir, rel_url, img_dir = qrcode_cy(filepath_name)
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir, rel_url, img_dir


def get_whole_url(url: str):
    config = get_config()
    return '{}{}'.format(config['template_url'], url)


def validate_mobile(value):
    import re
    REG_MOBILE = r'^\d{11}$'
    R_MOBILE = re.compile(REG_MOBILE)
    if not R_MOBILE.match(value):
        return False
    return True


def truncate_float(number):
    # 向下取保留两位数字
    return int(number * 100) / 100
