from django_q.tasks import async_task


@async_task
def coupon_import_task(pk: int):
    from coupon.models import UserCouponImport
    # 导入任务
    UserCouponImport.do_coupon_import_task(pk)
