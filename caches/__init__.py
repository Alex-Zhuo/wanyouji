# coding: utf-8
import contextlib
from contextlib import contextmanager
import os
from redis import StrictRedis
import time
from common.config import get_config


def get_prefix():
    redis_conf = get_config().get('redis')
    return redis_conf['prefix']


def get_redis_name(name):
    prefix = get_prefix()
    return prefix + '_' + name

def redis_client():
    redis_conf = get_config().get('redis')
    return StrictRedis(host=redis_conf.get('host', '127.0.0.1'), db=redis_conf.get('db', 0),
                       decode_responses=True)


_redis = redis_client()
sms_url = get_redis_name('sms_url')
session_info_recent_qs = get_redis_name('session_info_recent_qs')
session_info_recommend_qs = get_redis_name('session_info_recommend_qs')
commission_balance_key = get_redis_name('commission_balance_key')
commission_balance_lock_key = get_redis_name('commission_balance_lock_key{}')
seat_lock = get_redis_name('seat_lock{}')
performer_key = get_redis_name('performer_key')
performer_lock_key = get_redis_name('performer_lock_key{}')
city_key = get_redis_name('city_key')
session_seat_key = get_redis_name('session_seat_{}_{}')
check_code_key = get_redis_name('check_code_key_{}_{}')
pull_tiktok_qual_data = get_redis_name('pull_tiktok_qual_data')
pull_tiktok_goods = get_redis_name('pull_tiktok_goods_{}')
set_price_seat = get_redis_name('set_price_seat')
mz_error_log_key = get_redis_name('mz_error_log_key_{}_{}')
mz_error_sms_key = get_redis_name('mz_error_sms_key')
pika_session_seat_key = get_redis_name('pika_session_seat_{}')
pika_level_seat_key = get_redis_name('pika_level_seat_{}_{}')
# 旧的pika_session_seat_list_key，已作废
pika_session_seat_list_key = get_redis_name('pika_session_seat_list_key_{}')
pika_session_layer = get_redis_name('pika_session_layer')
pika_session_mz_layer = get_redis_name('pika_session_mz_layer')
pika_auto_sync_mai_zuo_key = get_redis_name('pika_auto_sync_mai_zuo_key')
pika_copy_goods = get_redis_name('pika_copy_goods')
level_sales_key = get_redis_name('level_sales_key')
level_sales_key_lock = get_redis_name('level_sales_key_lock{}')
ticket_order_refund_key = get_redis_name('ticket_order_refund_key')
update_goods_stock_lock = get_redis_name('update_goods_stock_lock{}')
receipt_pay_key = get_redis_name('receipt_pay_key_lock{}')
pika_down_key = get_redis_name('pika_down_key_{}')
session_actual_amount_key = get_redis_name('session_actual_amount_key')
scroll_key = get_redis_name('scroll_key')
pika_show_calendar_key = get_redis_name('pika_show_calendar_key_{}')
pika_session_mz_buy = get_redis_name('pika_session_mz_buy')
check_cps_source_key = get_redis_name('check_cps_source_key_{}')
theater_card_order_create_key = get_redis_name('theater_card_order_creat_{}')
add_discount_total_key = get_redis_name('add_discount_total_key')
theater_card_add_amount_key = get_redis_name('theater_card_add_amount_key_{}')
theater_card_detail_add_amount_key = get_redis_name('theater_card_detail_add_amount_key_{}')
redis_shows_no_key = get_redis_name('redis_shows_no_key')
redis_shows_copy_key = get_redis_name('redis_shows_copy_key')
redis_show_date_copy = get_redis_name('redis_show_date_copy')
redis_venues_copy_key = get_redis_name('redis_venues_copy_key')
redis_show_type_copy_key = get_redis_name('redis_show_type_copy_key')
redis_show_content_copy_key = get_redis_name('redis_show_content_copy_key')
redis_show_content_second_key = get_redis_name('redis_show_content_second_key')
redis_session_no_key = get_redis_name('redis_session_no')
redis_session_info_copy = get_redis_name('redis_session_info_copy')
redis_session_info_tiktok_copy = get_redis_name('redis_session_info_tiktok_copy')
redis_ticket_level_cache = get_redis_name('redis_ticket_level_cache_{}')
redis_ticket_level_tiktok_cache = get_redis_name('redis_ticket_level_tiktok_cache_{}')
third_cat_list = get_redis_name('third_cat_list')
export_ticket_order_key = get_redis_name('export_ticket_order_key')

stl_user_num = get_redis_name('stl_user_num')
stl_super_card_num = get_redis_name('stl_super_card_num')
stl_super_amount = get_redis_name('stl_super_amount')
stl_super_order_num = get_redis_name('stl_super_order_num')
stl_super_rest_amount = get_redis_name('stl_super_rest_amount')
stl_year_card_num = get_redis_name('stl_year_card_num')
stl_session_num = get_redis_name('stl_session_num')
stl_dy_amount = get_redis_name('stl_dy_amount')
stl_wx_amount = get_redis_name('stl_wx_amount')
stl_dy_live_order_num = get_redis_name('stl_dy_live_order_num')
stl_dy_video_order_num = get_redis_name('stl_dy_video_order_num')
stl_dy_order_num = get_redis_name('stl_dy_order_num')
stl_wx_order_num = get_redis_name('stl_wx_order_num')
stl_refund_num = get_redis_name('stl_refund_num')
stl_refund_amount = get_redis_name('stl_refund_amount')
stl_agent_num = get_redis_name('stl_agent_num')
stl_share_award_amount = get_redis_name('stl_share_award_amount')
stl_group_award_amount = get_redis_name('stl_group_award_amount')
stl_withdraw_amount = get_redis_name('stl_withdraw_amount')
stl_total_award_amount = get_redis_name('stl_total_award_amount')
day_session_num = get_redis_name('day_session_num')
day_order_sum = get_redis_name('day_order_sum')
city_order_sum = get_redis_name('city_order_sum')
month_order_sum = get_redis_name('month_order_sum')
code_img_key = get_redis_name('code_img_{}_{}')
change_price_key = get_redis_name('change_price_key_{}')
margin_order_key = get_redis_name('margin_order_key_{}')
user_key_order_key = get_redis_name('user_key_order_key_{}')
approve_act_key = get_redis_name('approve_act_key_{}')
common_cps_key = get_redis_name('common_cps_key_{}')
change_sale_time_key = get_redis_name('change_sale_time_key_{}')
set_refund_key = get_redis_name('set_refund_key_{}')
session_sum_key = get_redis_name('session_sum_key')
session_sum_key_lock = get_redis_name('session_sum_key_lock')
session_agent_sum_key = get_redis_name('session_agent_sum_key')
session_agent_sum_key_lock = get_redis_name('session_agent_sum_key_lock')
session_cps_sum_key = get_redis_name('session_cps_sum_key')
session_cps_sum_key_lock = get_redis_name('session_cps_sum_key_lock')
auth_check_code_tiktok_key = get_redis_name('auth_check_code_tiktok_key')
redis_session_info_ks_copy = get_redis_name('redis_session_info_ks_copy')
redis_session_info_xhs_copy = get_redis_name('redis_session_info_xhs_copy')
redis_ticket_level_ks_cache = get_redis_name('redis_ticket_level_ks_cache_{}')
redis_ticket_level_xhs_cache = get_redis_name('redis_ticket_level_xhs_cache_{}')
auth_report_order_ks_key = get_redis_name('auth_report_order_ks_key')
real_name_buy_session_key = get_redis_name('real_name_buy_session_key_{}')
real_name_buy_id_card_key = get_redis_name('real_name_buy_key_{}')
give_code_key = get_redis_name('give_code_key_{}')
give_cancel_key = get_redis_name('give_cancel_key')
lock_seat_key = get_redis_name('lock_seat_key_{}')
lock_cancel_seat_key = get_redis_name('lock_cancel_seat_key_{}')
account_info_cache_key = get_redis_name('account_info_cache_key_{}')
cache_show_detail_key = get_redis_name('cache_show_detail_key_{}')
settle_order_award_key = get_redis_name('settle_order_award')
cache_token_share_code_key = get_redis_name('token_sc_{}')
cache_share_code_user_key = get_redis_name('sc_user_{}')
cache_share_code_account_flag_key = get_redis_name('sc_flag_{}')
cache_user_new_parent_key = get_redis_name('user_np_{}')
save_model_key = get_redis_name('save_m_{}')
show_project_change_key = get_redis_name('showp_c_{}')
show_collect_copy_key = get_redis_name('show_collect_copy_key')
cache_order_session_key = get_redis_name('cache_order_session_{}')
cache_order_seat_key = get_redis_name('cache_order_seat_{}_{}')
matrix_seat_data_key = get_redis_name('matrix_seat_data_key_{}')


def get_redis_with_db(db: int) -> StrictRedis:
    if not (db and 0 <= db <= 15):
        raise ValueError(f"{db} must between 0 - 15")
    return StrictRedis(host=get_config().get('host', '127.0.0.1'), decode_responses=True, db=db)


@contextmanager
def with_redis():
    yield _redis


def get_redis():
    return _redis


def publish(channel, msg):
    with with_redis() as cli:
        cli.publish(channel, msg)


def push(key, msg):
    with with_redis() as cli:
        return cli.rpush(key, msg)


def normal_set(key, msg, ex=None):
    with with_redis() as cli:
        return cli.set(key, msg, ex=ex)


def get_by_key(key):
    with with_redis() as cli:
        return cli.get(key)


def hset(name, key, value, ex=None):
    with with_redis() as cli:
        cli.hset(name=name, key=key, value=value)
        if ex:
            cli.expire(name, time=ex)


def hget(name, key):
    with with_redis() as cli:
        return cli.hget(name=name, key=key)


@contextmanager
def with_redis_subscribe():
    _redis.pubsub().subscribe()
    yield _redis


def subscribe(channel, func):
    with with_redis_subscribe() as _cli:
        pubsub = _cli.pubsub()
        pubsub.subscribe(**{channel: func})
        return pubsub


def get_pika_redis():
    from common.config import get_config
    config = get_config()
    pika = config.get('pika')
    host = pika.get('host')
    port = pika.get('port')
    db = pika.get('db')
    return StrictRedis(host=host, port=port, db=db, decode_responses=True)


def check_lock_time_out(lock_key, time_out=5):
    st = False
    key = get_redis_name(lock_key)
    with with_redis() as redis:
        if redis.setnx(key, 1):
            redis.expire(key, time_out)
            st = True
    if not st:
        from restframework_ext.exceptions import CustomAPIException
        raise CustomAPIException('请勿重复操作')


class LockResult:
    def __init__(self, result: bool, try_times: int = 1, wait_seconds: int = 0):
        self._result = result
        self._try_times = try_times
        self._wait_seconds = wait_seconds

    def __str__(self):
        return f"result:{self._result},try_times:{self.try_times},wait_seconds:{self.wait_seconds}"

    def __bool__(self):
        return self._result

    @property
    def try_times(self):
        return self._try_times

    @property
    def wait_seconds(self):
        return self._wait_seconds


def acquire_lock(lock_key: str, expire: int = 10, wait_timeout: int = 0, owner: str = None) -> LockResult:
    """
    分布式锁，防止并发修改
    lock key base on redis
    @param expire, the key expire time, must be positive
    @param wait_timeout acquire wait timeout in seconds, must be positive, because blocking process
    @param owner the owner who acquires the lock, default to pid
    @return bool
    """
    red = get_redis()
    if not owner:
        owner = str(os.getpid())
    if (not isinstance(wait_timeout, int)) or wait_timeout < 0:
        wait_timeout = 0
    if (not isinstance(expire, int)) or expire <= 0:
        expire = 1
    success = False
    if wait_timeout > 0:
        cp = wait_timeout
        try_times = 0
        while wait_timeout > 0:
            success = red.setnx(lock_key, owner)
            try_times += 1
            if success:
                red.expire(lock_key, expire)
                return LockResult(success, try_times, cp - wait_timeout)
            time.sleep(1)
            wait_timeout -= 1
        return LockResult(success, try_times, cp - wait_timeout)
    else:
        success = red.setnx(lock_key, owner)
        if success:
            red.expire(lock_key, expire)
        return LockResult(success)


def release_lock(lock_key: str, owner: str = None):
    red = get_redis()
    if not owner:
        owner = str(os.getpid())
    actual_owner = red.get(lock_key)
    if actual_owner and actual_owner == owner:
        red.delete(lock_key)


@contextlib.contextmanager
def run_with_lock(lock_key: str, expire: int = 10, wait_timeout: int = 0, owner: str = None) -> LockResult:
    try:
        yield acquire_lock(lock_key, expire, wait_timeout, owner)
    # except Exception as e:
    #     print(f"acceive exception : {e}")
    #     raise TypeError('reraise')
    finally:
        # print('auto release')
        release_lock(lock_key, owner)
        # print('auto release over')


class RedisCounter:
    @staticmethod
    def increment(key, max_value=None):
        """
        原子递增计数器
        :param key: 计数器键
        :param max_value: 最大值(可选)
        :return: 递增后的值或None(如果超过最大值)
        使用Lua脚本来执行原子操作，Lua脚本在服务器上作为一个单一的操作执行，这意味着它可以确保在脚本执行期间不会被其他命令打断
        """
        lua_script = """
        local current = redis.call('GET', KEYS[1])
        if not current then
            current = 0
            redis.call('SET', KEYS[1], current)
        end

        if tonumber(ARGV[1]) and tonumber(current) >= tonumber(ARGV[1]) then
            return nil
        end

        local new_value = redis.call('INCR', KEYS[1])
        return new_value
        """
        redis_client = get_redis()
        result = redis_client.eval(lua_script, 1, key, max_value or '')
        return int(result) if result else None
