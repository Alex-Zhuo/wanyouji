# coding: utf-8
use_open_platform = False

# 'snsapi_userinfo'
default_scope_type = 'snsapi_base'

domain = u'http://myi.liyunmall.com'

url_prefix = domain + u'/mpweb/?next={}&append=1'

notify_url = domain + u'/api/receipts/notify/'

mp_first_industry_id = 1
mp_second_industry_id = 31

subscribe_reply_content = '您好，感谢关注'
scan_reply_content = '您好，感谢关注'