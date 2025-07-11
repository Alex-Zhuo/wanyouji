# coding: utf-8
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from mall.models import User
from shopping_points.models import UserAccount

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_account_when_create_user(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    user = kwargs.get('instance')
    if created:
        UserAccount.create(user)
        from statistical.models import TotalStatistical
        TotalStatistical.add_user_num()
    if not user.share_code:
        user.get_share_code()
    if created or update_fields:
        # 用户表里的token不刷新
        from mall.user_cache import share_code_user_cache
        share_code_user_cache(user, True)


@receiver(post_save, sender=UserAccount)
def account_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    is_create = False
    if created:
        if instance.is_agent():
            is_create = True
    else:
        if update_fields and 'flag' in update_fields:
            if instance.is_agent():
                is_create = True
            else:
                from mall.user_cache import share_code_account_flag_cache_delete
                share_code_account_flag_cache_delete(instance.user.share_code)
    if is_create:
        from mall.user_cache import share_code_account_flag_cache
        user = instance.user
        share_code_account_flag_cache(user.share_code, user.id, instance.flag)