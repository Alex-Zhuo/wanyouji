# coding: utf-8
import logging
from typing import Callable

from redis import Redis

log = logging.getLogger(__name__)

_redis_provider: Callable = None


def set_redis_provider(func: Callable):
    global _redis_provider
    if _redis_provider:
        log.warning(f"repeated set redis provider, from {_redis_provider} to {func}")
    _redis_provider = func


def get_redis() -> Redis:
    """
        todo: 真实环境
        """
    # from caches import get_redis
    # return get_redis()
    if not _redis_provider:
        raise ValueError(f"haven't set redis provider")
    return _redis_provider()  # redis.Redis()
