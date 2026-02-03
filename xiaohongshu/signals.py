# coding: utf-8
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from xiaohongshu.models import XhsGoodsConfig

logger = logging.getLogger(__name__)


@receiver(post_save, sender=XhsGoodsConfig)
def xhs_good_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    logger.error(update_fields)
    if update_fields:
        if 'status' in update_fields or 'push_status' in update_fields:
            instance.session.change_show_calendar()
    instance.session.redis_show_date_copy()
