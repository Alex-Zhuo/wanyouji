# coding: utf-8
import os
import json
import requests

from decouple import config

# urlshare_index
share_index = '/static/front/store/?#/pages/index/index?share_code={}'
share_index_s = '/static/front/store/?#/pages/index/index'
share_index_center = '/static/front/store/?#/pages/center/center'
share_url_reg = '/static/front/mobile/html/register.html?sc={}'
share_url_index = '/static/front/mobile/html/cate.html?sc={}'
share_url_good = '/static/front/mobile/html/goodsDetail.html?id={}&sc={}'
order_detail_url = '/static/front/?#/orderDetail?id={}'
mall_index = '/static/front/store/?s=1#/index'
mobile_mall_decorate = '/static/front/editor/index.html#/editor_mobile?page_code=mobile_front_config'
official_site_decorate = '/static/front/editor/index.html#/website'
pc_mall_decorate = '/static/front/website/index.html#/editor_index'
notify_url = '/api/receipts/notify/'
refund_notify_url = '/api/receipts/refund_notify/'
umf_notify_url = '/api/receipts/umf_notify/'
front_notify_url = '/static/front/store/?#/paySuccess?receipt={}&url_prefix={}'
relation_url = '/static/front/store/relations/relations.html'
host = 'http://ym.ccvp.top'
qrcode_filename_salt = 'xsa!@#!@#xxsad123asdkalsdjl'
user_share_code_salt = 'as#7dsf-d'
admin_url_site_name = config('admin_url_site_name', default='admin')

normal_user_group_id = 999
general_admin_group_id = 1000
vendor_group_id = 1002
temp_vendor_group_id = 1003
support_staff_group_id = 1004
forum_staff_group_id = 1005
city_manager_group_id = 1006

vendor_user_id_start = 24806689
temp_vendor_password = 'ly123456'

default_pay_type = 1
rsa_public_key_path = 'static/public.pem'


class MallBaseConfig(object):
    path = 'static/config.json'

    @classmethod
    def get_path(cls):
        from django.conf import settings
        return os.path.join(settings.BASE_DIR, cls.path)

    @classmethod
    def get_base_config(cls):
        if not os.path.isfile(cls.path):
            return {'mall_name': u'商城'}
        with open(cls.get_path()) as f:
            data = json.load(f)
        return data

    @classmethod
    def override_config(cls, data_dict):
        with open(cls.path, 'w') as f:
            json.dump(data_dict, f)


def get_binding_mp():
    resp = requests.get(
        'http://open.liyunmall.com/api/mpclient/{}/auth_check/'.format(os.environ.get('INSTANCE_TOKEN')))
    if resp.status_code != 404:
        return resp.json()
    else:
        return None


class MallSettings(object):

    @property
    def withdraw_type(self):
        # 提醒方式 1:银行卡 2: 零钱
        return config('withdraw_type', default=1, cast=int)

    @property
    def express_api_appcode(self):
        from common.config import get_config
        config = get_config()
        return config['express_api_appcode']

    @property
    def monthly_bonus_ratio(self):
        return config('monthly_bonus_ratio', default=0.1, cast=float)

    @property
    def order_expire_seconds(self):
        return config('order_expire_seconds', default=900, cast=int)


MallSettings = MallSettings()
