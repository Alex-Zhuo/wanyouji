from django_q.tasks import async_task


def coupon_import_task(pk: int):
    from coupon.models import UserCouponImport
    # 导入任务
    async_task(UserCouponImport.do_coupon_import_task, pk)
    # UserCouponImport.do_coupon_import_task(pk)


# def coupon_update_stock_from_redis():
#     from coupon.models import Coupon
#     Coupon.coupon_update_stock_from_redis()
