import logging
from typing import List, Type, Union

from concu.stock_cache import StockCache, StockModel
from ticket.models import TicketFile, SessionInfo

"""
实现库存的缓存
"""


class PrizeStockCache(StockCache):
    def load_list(self) -> List[StockModel]:
        l = []
        from blind_box.models import Prize
        for _id, stock in Prize.objects.values_list('pk', 'stock'):
            l.append(StockModel(_id, stock))
        return l

    def key_prefix(self):
        return 'prize-stock'

    def save_stock_model(self, id: Union[int, str], qty: int):
        from blind_box.models import Prize
        return Prize.objects.filter(pk=id).update(stock=qty) == 1


prsc = PrizeStockCache()
