def coupon_update_stock_from_redis():
    from coupon.models import Coupon
    Coupon.coupon_update_stock_from_redis()
