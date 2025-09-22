# coding:utf-8
from django.core.cache import cache
from caches import cache_share_code_user_key, cache_token_share_code_key, cache_share_code_account_flag_key, \
    cache_user_new_parent_key
from datetime import datetime
import logging
log = logging.getLogger(__name__)
# token 72小时过期
TOKEN_EXPIRE_HOURS = 24
# share_code-> user 90天过期
SHARE_CODE_USER_EXPIRE = 3 * 30 * 24 * 3600


def token_share_code_cache(token: str, share_code: str, is_refresh=True):
    """
    token->share_code缓存，登录后生成自动生成
    """
    key = cache_token_share_code_key.format(token)
    if not is_refresh:
        expire_in = cache.ttl(key)
    else:
        expire_in = TOKEN_EXPIRE_HOURS * 3600 - 10
    if expire_in > 0:
        cache.set(key, share_code, expire_in)


def token_share_code_cache_delete(token: str):
    """
    token->share_code 删除,没用到，3天会自动过期
    """
    key = cache_token_share_code_key.format(token)
    cache.delete(key)


def share_code_user_cache(user, need_search=False):
    """
    share_code->user缓存
    """
    if need_search:
        """执行save()，会把关联表数据也缓存，所以要重新搜索一次"""
        from mall.models import User
        user = User.objects.filter(id=user.id).first()
    if user:
        key = cache_share_code_user_key.format(user.share_code)
        cache.set(key, user, SHARE_CODE_USER_EXPIRE)
        # log.error(cache.ttl(key))


def share_code_user_cache_delete(share_code: str):
    """
     share_code->user 删除
    """
    key = cache_share_code_user_key.format(share_code)
    cache.delete(key)


def share_code_account_flag_cache(share_code: str, user_id: int, flag: int):
    """
    share_code>dict(用户id，flag) 永久存pika (需要初始化,需要维护，记录下最后的id，运行后补漏掉的新用户)
    signal用户身份改变时增加或删除，用来判断是否可以绑定最新上级
    """
    # timeout=None 代表永久
    key = cache_share_code_account_flag_key.format(share_code)
    data = dict(user_id=user_id, flag=flag)
    cache.set(key, data, timeout=None)


def share_code_account_flag_cache_delete(share_code: str):
    """
    share_code->flag
    """
    key = cache_share_code_account_flag_key.format(share_code)
    cache.delete(key)


def user_new_parent_cache(user_id: int, parent_id: int, parent_share_code: str, name: str, date_at: datetime = None):
    """
    用户id->dict（时间，最新推荐人id，share_code,名称：get_full_name ）永久存pika
    (需要初始化['取最新推荐人没有则取固定推荐人':旧逻辑]，记录下最后的id，运行后补漏掉的新用户。后面新用户创建signal生成))
    (后台展示修改，下单的时候使用：用share_code 取User对象 pika)
    """
    key = cache_user_new_parent_key.format(user_id)
    date_at_timestamp = None
    if date_at:
        from common.utils import get_timestamp
        date_at_timestamp = int(get_timestamp(date_at) / 1000)
    data = dict(parent_id=parent_id, parent_share_code=parent_share_code, date_at_timestamp=date_at_timestamp,
                name=name)
    cache.set(key, data, timeout=None)


def user_new_parent_cache_delete(user_id: int):
    """
    用户id->最新上级删除，没必要不需要删除，合并的也不需要删，后台需要看
    """
    key = cache_user_new_parent_key.format(user_id)
    cache.delete(key)


def get_user_new_parent(user_id: int):
    """
    用户id->最新上级
    """
    key = cache_user_new_parent_key.format(user_id)
    return cache.get(key)


def token_to_cache_user(token: str):
    """
    token获取user
    """
    user = None
    token_key = cache_token_share_code_key.format(token)
    share_code = cache.get(token_key)
    if share_code:
        user = share_code_to_user(share_code)
    return user


def share_code_to_user(share_code: str):
    """
    share_code获取user
    """
    share_code_key = cache_share_code_user_key.format(share_code)
    return cache.get(share_code_key)


def init_user_all_cache(user_list):
    """
    需要初始化：
    share_code ->user对象pika, 返回最后的id，运行后补漏掉的新用户
    用户id->最新推荐人
    """
    user_id = None
    for user in user_list:
        if not user.share_code:
            # 更新share_code，singal会share_code_to_user
            user.get_share_code()
        else:
            share_code_user_cache(user)
        # 最新推荐人初始化
        init_user_new_parent_cache(user)
        user_id = user.id
    return user_id


def init_user_new_parent_cache(user):
    """"
    最新推荐人初始化
    3.1用户id->dict（时间，最新推荐人id，share_code,名称：get_full_name ）永久存pika
    (需要初始化['取最新推荐人没有则取固定推荐人':旧逻辑]，记录下最后的id，运行后补漏掉的新用户。后面新用户创建signal生成))
    (后台展示修改，下单的时候使用：用share_code 取User对象 pika)
    """
    parent = None
    date_at = None
    if user.new_parent:
        parent = user.new_parent
        date_at = user.new_parent_at
    elif user.parent and user.parent.account.is_agent():
        parent = user.parent
        date_at = user.parent_at
    if parent:
        user_new_parent_cache(user_id=user.id, parent_id=parent.id, parent_share_code=parent.share_code,
                              date_at=date_at, name=parent.get_full_name())


def init_account_flag_cache(account_list):
    """
    share_code>dict(用户id，flag) 永久存pika (需要初始化,需要维护，记录下最后的id，运行后补漏掉的新用户)
    signal用户身份改变时增加或删除，用来判断是否可以绑定最新上级
    """
    account_id = None
    for account in account_list:
        user = account.user
        share_code_account_flag_cache(user.share_code, user.id, account.flag)
        account_id = account.id
    return account_id


def login_refresh_cache(token, user):
    token_share_code_cache(token, user.share_code)
    user.token = token
    share_code_user_cache(user, True)


def change_new_parent(new_user_id: int, old_user_id: int):
    new_parent_cache = get_user_new_parent(new_user_id)
    if new_parent_cache:
        key = cache_user_new_parent_key.format(old_user_id)
        # 设到旧的用户上面覆盖
        cache.set(key, new_parent_cache, timeout=None)
        # user_new_parent_cache_delete(new_user_id)


def bind_new_parent(user_id: int, parent):
    parent_share_code = parent.share_code
    flag_key = cache_share_code_account_flag_key.format(parent_share_code)
    flag_data = cache.get(flag_key)
    # 满足身份
    if flag_data:
        user_new_parent_cache(
            user_id=user_id, parent_id=parent.id, parent_share_code=parent_share_code, name=parent.get_full_name(),
            date_at=datetime.now())


def get_new_parent_cache(user_id: int):
    parent = None
    new_parent = get_user_new_parent(user_id)
    if new_parent:
        parent_share_code = new_parent['parent_share_code']
        flag_key = cache_share_code_account_flag_key.format(parent_share_code)
        flag_data = cache.get(flag_key)
        # 满足身份
        if flag_data:
            parent = share_code_to_user(parent_share_code)
    return parent


def page_init_user_cache():
    from mall.models import User
    import time
    # 先初始化用户
    start = 0
    add = 3000
    end = 3000
    user_list = True
    end_user_id = None
    while user_list:
        user_list = User.objects.filter(is_active=True)[start:end]
        if user_list:
            end_user_id = init_user_all_cache(user_list)
            time.sleep(3)
            start = end
            end = end + add
        else:
            break
    # 再初始化代理身份
    from shopping_points.models import UserAccount
    account_list = UserAccount.objects.filter(flag__in=[2, 3])
    # 返回的id为，最后的accountid
    end_account_id = init_account_flag_cache(account_list)
    return end_user_id, end_account_id
