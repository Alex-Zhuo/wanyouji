from celery import shared_task
import logging

log = logging.getLogger(__name__)
from coupon.models import Coupon, UserCouponRecord


@shared_task
def coupon_expire_task():
    Coupon.auto_off_task()
    UserCouponRecord.check_expire_task()
