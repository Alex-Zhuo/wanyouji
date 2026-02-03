# coding: utf-8
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from coupon.models import Coupon

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Coupon)
def coupon_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if created or (update_fields and 'stock' in update_fields):
        instance.coupon_redis_stock()


@receiver(post_delete, sender=Coupon)
def coupon_delete(sender, **kwargs):
    instance = kwargs.get('instance')
    instance.coupon_del_redis_stock()
