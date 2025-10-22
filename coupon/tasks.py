from celery import shared_task
import logging

log = logging.getLogger(__name__)
from coupon.models import Coupon, UserCouponRecord, UserCouponImport, UserCouponCacheRecord


@shared_task
def coupon_expire_task():
    Coupon.auto_off_task()
    UserCouponRecord.check_expire_task()


@shared_task
def coupon_bind_user_task(mobile: str, user_id: int):
    # 绑定消费券
    UserCouponCacheRecord.do_bind_user_task(mobile, user_id)


@shared_task
def coupon_update_stock_from_redis():
    Coupon.coupon_update_stock_from_redis()
