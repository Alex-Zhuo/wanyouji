from celery import shared_task
import logging

log = logging.getLogger(__name__)
from coupon.models import Coupon, UserCouponRecord, UserCouponImport, UserCouponCacheRecord


@shared_task
def coupon_expire_task():
    Coupon.auto_off_task()
    UserCouponRecord.check_expire_task()


@shared_task
def coupon_import_task(pk: int):
    # 导入任务
    UserCouponImport.do_coupon_import_task(pk)


@shared_task
def coupon_bind_user_task(mobile: str, user_id: int):
    # 导入任务
    UserCouponCacheRecord.do_bind_user_task(mobile, user_id)
