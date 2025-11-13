import logging
from typing import List, Type, Union

from concu.stock_cache import StockCache, StockModel

"""
实现库存的缓存
"""


class CouponStockCache(StockCache):
    def load_list(self) -> List[StockModel]:
        l = []
        from coupon.models import Coupon
        for _id, stock in Coupon.objects.values_list('pk', 'stock'):
            l.append(StockModel(_id, stock))
        return l

    def key_prefix(self):
        from caches import get_redis_name
        return get_redis_name('coupon-stock')

    def save_stock_model(self, id: Union[int, str], qty: int):
        from coupon.models import Coupon
        return Coupon.objects.filter(pk=id).update(stock=qty) == 1


csc = CouponStockCache()
