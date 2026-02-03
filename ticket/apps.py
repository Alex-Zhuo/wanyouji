# coding=utf-8
from __future__ import unicode_literals

from django.apps import AppConfig


class TicketConfig(AppConfig):
    name = 'ticket'
    verbose_name = '演出管理'

    def ready(self):
        from ticket import signals
        from user_agents import parsers
        from functools import partial
        parsers.MOBILE_BROWSER_FAMILIES = parsers.MOBILE_BROWSER_FAMILIES + ('Chrome Mobile',)
        from concu import set_redis_provider
        from caches import get_redis_with_db
        set_redis_provider(partial(get_redis_with_db, db=3))
        # from ticket.models import ShowProject
        # ShowProject.init_all_cache()
