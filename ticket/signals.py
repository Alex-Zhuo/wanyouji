# coding: utf-8
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from ticket.models import TicketOrderRefund, SessionInfo, ShowType, ShowContentCategory, Venues, ShowProject, \
    TicketFile, ShowsDetailImage, TicketOrder, ShowCollectRecord, ShowContentCategorySecond

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TicketOrderRefund)
def ticket_refund_finished(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if update_fields and 'status' in update_fields:
        if instance.status == TicketOrderRefund.STATUS_FINISHED:
            instance.ticket_refund_back()


@receiver(post_save, sender=SessionInfo)
def sessioninfo_change_status(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if update_fields:
        if 'status' in update_fields or 'dy_status' in update_fields:
            instance.change_show_calendar()
    if created or update_fields:
        instance.redis_show_date_copy()
    if created:
        from statistical.models import TotalStatistical
        TotalStatistical.add_session_num()


@receiver(post_save, sender=ShowType)
def show_type_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if created or update_fields:
        instance.show_type_copy_to_pika()


@receiver(post_save, sender=ShowContentCategory)
def show_content_category_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    # if created or update_fields:
    instance.show_content_copy_to_pika()


@receiver(post_save, sender=ShowContentCategorySecond)
def show_content_second_category_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    # if created or update_fields:
    instance.show_content_second_copy_to_pika()


@receiver(post_save, sender=Venues)
def venues_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if created or update_fields:
        instance.venues_detail_copy_to_pika()


@receiver(post_save, sender=ShowProject)
def show_project_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if update_fields:
        discard_list = ['wxa_code', 'qualification_identity', 'host_approval_qual', 'ticket_agent_qual',
                        'wx_pay_config', 'dy_pay_config']
        update_fields = set(update_fields)
        for dd in discard_list:
            update_fields.discard(dd)
            if not update_fields:
                break
    logger.debug(update_fields)
    if created or update_fields:
        instance.shows_detail_copy_to_pika()


@receiver(post_save, sender=TicketFile)
def ticket_file_change(sender, **kwargs):
    # 放在了具体代码里了
    pass
    # created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    # if created or update_fields:
    #     instance.redis_ticket_level_cache()


@receiver(post_save, sender=ShowsDetailImage)
def showsdetailimage_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    instance.shows_detail_images_copy_to_pika()


@receiver(post_delete, sender=ShowsDetailImage)
def showsdetailimage_delete(sender, **kwargs):
    logger.debug('showsdetailimagedelete')
    instance = kwargs.get('instance')
    instance.shows_detail_images_copy_to_pika()


@receiver(post_save, sender=ShowCollectRecord)
def show_collect_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if created or update_fields:
        instance.show_collect_copy_to_pika()
