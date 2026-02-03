import time
from typing import List, Tuple, Union

from concu import get_redis


class StockModel:
    def __init__(self, _id: Union[int, str], stock: int):
        self._id: Union[int, str] = _id
        self._stock = stock

    def __str__(self):
        return f'{self.id}-{self.stock}'

    @property
    def stock(self):
        return self._stock

    @stock.setter
    def stock(self, stock: int):
        self._stock = stock

    @property
    def id(self) -> Union[int, str]:
        return self._id

    @id.setter
    def id(self, val: Union[int, str]):
        self._id = val


class StockCache:
    def load_list(self) -> List[StockModel]:
        """
        加载需要预热的全量数据列表,用于预热(pre_cache)
        """
        raise NotImplementedError()

    def key_prefix(self):
        """
        数据的key前缀,比如商品可定位good.只要多种数据的缓存名称不冲突即可
        """
        raise NotImplementedError()

    def get_key(self, dest: str) -> str:
        return f"{self.key_prefix()}-{dest}"

    def save_stock_model(self, id: Union[int, str], qty: int) -> bool:
        """
        :param id 缓存id
        :param qty 缓存的最新数据
        """
        raise NotImplementedError()

    def cache_key(self, _id: Union[int, str]):
        return self.get_key(_id)

    def append_cache(self, sm: StockModel):
        """
        新增缓存单个.没有考虑是否已经缓存.
        """
        r = get_redis()
        r.set(self.cache_key(sm.id), sm.stock)

    def get_stock(self, _id: Union[int, str]):
        """
        移除缓存.删除数据时调用
        """
        r = get_redis()
        return r.get(self.cache_key(_id))

    def pre_cache(self):
        """
        1.加载数据，预热缓存
        """
        r = get_redis()
        for sm in self.load_list():
            r.setnx(self.cache_key(sm.id), sm.stock)

    def get_update_ts_key(self):
        """
        保存商品的数据更新时间和持久化时间的字典的key
        例如good-update-ts
        """
        return self.get_key('update-ts')

    # def incr_persist(self, id: Union[int, str], qty: int, increment:int):
    #     """
    #     :param id, 标识id
    #     :param qty, 缓存里新的库存数量
    #     :param increment,
    #     持久化.一般为非同步方式,将要更新的数据
    #     """
    #     pass

    def record_update_ts(self, id: Union[int, str]):
        """
        :param 记录id的数据更新时间戳(s),辅助后面的更新

        good-update_ts:
           {"1-upd": 1009912899, "1-per": 10080091900}
           其中 1-upd代表商品id=1的最新更新的时间, 1-per代表商品id=1的最新持久化时间.只要1-upd > 1-per就可以更新
        """
        r = get_redis()
        r.hset(self.get_update_ts_key(), f'{id}-upd', int(time.time()))

    def record_persist_ts(self, _id: Union[int, str]):
        """
        记录持久化时间
        """
        r = get_redis()
        r.hset(self.get_update_ts_key(), f'{_id}-per', int(time.time()))

    def incr(self, id: Union[int, str], increment: int, ceiling: int = 0, disable_record_update_ts: bool = False) -> \
            Tuple[bool, int]:
        """
        :param ceiling 计数后要大于ceiling, 比如库存通常要求减库存后大于0. 传Ellipsis代表不限制
        1.更新缓存
        2.更新数据库（采取定期同步缓存的到数据库).
        :return bool, int 是否计数成功, 计数后的新值, 若为false, 新值为0
        """
        r = get_redis()
        ck = self.cache_key(id)
        ret = r.incr(ck, increment)
        if ceiling == Ellipsis:
            return True, ret
        if ret < ceiling:
            r.incr(ck, -increment)
            return False, 0
        else:
            if not disable_record_update_ts:
                self.record_update_ts(id)
            return True, ret

    def batch_incr(self, inc_tuple: List[Tuple[Union[int, str], int, int]]) -> Tuple[
        bool, List[Tuple[Union[int, str], int]]]:
        """
        :param inc_tuple (id, increment, ceiling)
        批量减多个商品库存, 保证原子性,成功则全部更新成功,失败则回滚.
        返回: bool, List[Tuple[Union[int, str], int]  是否全部更新成功, 成功之后依次的新值; 失败是为False, []
        """
        l = []
        incred = []
        for _id, increment, ceiling in inc_tuple:
            succeed, qty = self.incr(_id, increment, ceiling, True)
            if not succeed:
                break
            else:
                l.append((_id, qty))
                incred.append((_id, increment))
        else:
            return True, l
        # means beak, so need to rollback
        for _id, increment in incred:
            self.incr(_id, -increment, Ellipsis, True)
        return False, []

    @staticmethod
    def resolve_ids(batch_results: List[Tuple[Union[int, str], int]]) -> List[Union[int, str]]:
        """
        工具方法, 对batch_incr的结果解析出batch_record_update_ts需要的参数结构.应用场景为:
        batch_incr->succeed->resolve_ids->batch_record_update_ts
        """
        return [o[0] for o in batch_results]

    def batch_record_update_ts(self, ids: List[Union[int, str]]):
        """
        批量设置更新时间戳.用在batch_incr之后.当跨表事务更新时候尤其需要用到
        """
        for _id in ids:
            self.record_update_ts(_id)

    def instant_persist(self, _id: Union[int, str]):
        """
        即时持久化单个,一般发生在后台更新商品库存时,需要单独更新,但又不想干扰定期持久化的流程.
        所以后台更新商品库存时，需要采取 增减方式, 且更新顺序为 缓存->数据库.
        后台发起更新库存操作为:
        self.incr(...)
        self.instant_persist(...)
        """
        uk = self.get_update_ts_key()
        r = get_redis()
        upd, per = r.hget(uk, f'{_id}-upd'), r.hget(uk, f'{_id}-per')
        if upd and (not per or int(per) < int(upd)):
            # update
            qty = r.get(self.cache_key(_id))
            if qty and self.save_stock_model(_id, int(qty)):
                self.record_persist_ts(_id)

    def persist(self):
        """
        定期执行, 遍历good-update-ts字典.全量持久化
        """
        uk = self.get_update_ts_key()
        r = get_redis()
        udict = r.hgetall(uk)
        uddict = {}
        for k, v in udict.items():
            _id, tp = k.split('-')
            o = {tp: int(v)}
            uddict.setdefault(_id, o).update(o)
        for _id, d in uddict.items():
            upd, per = d.get('upd'), d.get('per')
            if upd and (not per or per < upd):
                # update
                qty = r.get(self.cache_key(_id))
                if qty and self.save_stock_model(_id, int(qty)):
                    self.record_persist_ts(_id)

    def t_batch_incr(self, inc_tuple: List[Tuple[Union[int, str], int, int]]) -> 'BatchTrans':
        return BatchTrans(self, inc_tuple)

    def t_incr(self, id: Union[int, str], increment: int, ceiling: int = 0,
               disable_record_update_ts: bool = False) -> 'SingleTrans':
        return SingleTrans(id, increment, ceiling, disable_record_update_ts)

    def remove(self, _id: Union[int, str]):
        """
        移除缓存.删除数据时调用
        """
        r = get_redis()
        r.delete(self.cache_key(_id))
        uk = self.get_update_ts_key()
        r.hdel(uk, f'{_id}-upd'), r.hget(uk, f'{_id}-per')


class BatchTrans:
    def __init__(self, sc: StockCache, inc_tuple: List[Tuple[Union[int, str], int, int]]):
        self._inc_tuple = inc_tuple
        self._handle = sc
        self._ret: Tuple[bool, List[Tuple[Union[int, str], int]]] = None

    def __enter__(self):
        self._ret = self._handle.batch_incr(self._inc_tuple)
        return self._ret

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # rollback
            self._handle.batch_incr([(a, -b, Ellipsis) for a, b, c in self._inc_tuple])
        return False


class SingleTrans:
    def __init__(self, sc: StockCache, id: Union[int, str], increment: int, ceiling: int = 0,
                 disable_record_update_ts: bool = False):
        self._handle = sc
        self._id = id
        self._increment = increment
        self._ceiling = ceiling
        self._disable_record_update_ts = disable_record_update_ts
        self._ret = None

    def __enter__(self):
        self._ret = self._handle.incr(self._id, self._increment, self._ceiling, True)
        return self._ret

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._handle.incr(self._id, -self._increment, Ellipsis, True)
        else:
            if not self._disable_record_update_ts:
                self._handle.record_update_ts(self._id)
        return False
