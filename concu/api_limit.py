import contextlib
import logging
import random
import time
import typing
from typing import Callable

from redis.client import Redis
from concu import get_redis, set_redis_provider
from caches import get_redis_name

log = logging.getLogger(__name__)

"""
使用参考:
1.先set_redis_provider设置redis实例获取方法，后面获取实例使用该provider
2.使用try_queue排队, 参考main方法
"""

_get_redis = get_redis


def get_queue_size():
    r = _get_redis()
    key = get_redis_name('app-limit-queue-size')
    qs = r.get(key)
    if not qs:
        r.set(key, 20)
    try:
        ret = int(qs)
    except:
        ret = 20
    return ret if ret > 1 else 1


def get_max_wait():
    r = _get_redis()
    key = get_redis_name('app-limit-max-wait')
    qs = r.get(key)
    if not qs:
        r.set(key, 20)
    try:
        ret = int(qs)
    except:
        ret = 3
    return ret if ret > 1 else 3


class try2:
    def __init__(self, a: int):
        self._a = a + 1

    def __enter__(self):
        return self._a

    def __exit__(self, exc_type, exc_val, exc_tb):
        print((exc_type, exc_val, exc_tb))
        raise ValueError('sadas')
        # return True


# contextmanager在yield后无发抛出异常, 无论是with语句块里的异常还是yield后的异常,因此不满足需求.即它设计为不抛异常.所以只能用__enter__类实现，可以
# 精准控制异常. 参考: http://www.bjhee.com/python-context.html
# @contextlib.contextmanager
class try_queue:
    def __init__(self, queue: str, limit: int, max_wait: int = 3, sleep_func: Callable = None) -> typing.NoReturn:
        """
        @queue 队列名称
        @limit  最大队列数量
        @max_wait 最大等待时间,单位s
        @sleep_func 睡眠函数,默认time.sleep
        todo:需要考虑做完没有释放锁的情况,发生在incr之后，因为某些原因被终止执行，从而导致没有decr.
            方案是incr之后,存一个 k_timestamp 到 hash里,然后由其他进程对其做超时释放，释放包括decr k和删除k_timestamp.
            目前可以先不考虑,假设进程不会在decr前打断,可以定期手工检查一下这个队列是不是会保持在持续超过limit不下来的情况
        """
        self._queue = queue
        # raise ValueError('begin ex')
        if not isinstance(queue, str):
            raise TypeError(f'{queue} is not str')
        r = _get_redis()
        sleep_func = sleep_func or time.sleep

        while max_wait > 0:
            count: int = r.incr(queue)
            if count > limit:
                r.decr(queue)
                interval = random.random()
                sleep_func(interval)
                max_wait -= interval
            else:
                self._ret = True
                break
        else:
            self._ret = False

    def __enter__(self):
        return self._ret

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        若不想抛出异常则return True. 默认不返回值，也是抛出异常的
        """
        if self._ret:
            # 拿到锁了，执行完要重置队列
            r = _get_redis()
            r.decr(self._queue)
        return False


if __name__ == '__main__':
    # print('xbg')
    # # try:
    # with try2(1) as x:
    #     print(f"{x}")
    #     raise ValueError('x+111')
    # # except Exception as e:
    # #     print(f"{e} get")

    set_redis_provider(Redis)
    with try_queue('k', 3, 10) as gotted:
        if gotted:
            print("i get the queue")
            raise ValueError('go exception')
        else:
            print("get failed")
            raise ValueError('not exception')
    print('asd')
