# coding: utf-8
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from kuaishou_wxa.models import KsPoiService, KsGoodsImage, KsGoodsConfig
from ticket.models import TicketOrder

logger = logging.getLogger(__name__)


@receiver(post_save, sender=KsGoodsImage)
def ksgoodsimage_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    if created or not update_fields or (update_fields and 'ks_img_id' not in update_fields):
        try:
            instance.ks_upload_image()
        except Exception as e:
            logger.error(e)


@receiver(post_save, sender=KsGoodsConfig)
def ks_good_change(sender, **kwargs):
    created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
    logger.error(update_fields)
    if update_fields:
        if 'status' in update_fields or 'push_status' in update_fields:
            instance.session.change_show_calendar()
    instance.session.redis_show_date_copy()

# @receiver(post_save, sender=TicketOrder)
# def order_saved(sender, **kwargs):
#     """
#     注意: 当前这种实现, 要求order_instance.save(update_fields=['status'])中的update_fields包含status
#     :return:
#     """
#     created, instance, update_fields = map(kwargs.get, ('created', 'instance', 'update_fields'))
#     logger.debug('update_fields is {}'.format(update_fields))
#     if update_fields and 'status' in update_fields:
#         if instance.status == TicketOrder.STATUS_FINISH:
#             from kuaishou_wxa.models import KsOrderReportRecord
#             from mall.models import Receipt
#             if instance.status in KsOrderReportRecord.report_status():
#                 try:
#                     if instance.pay_type == Receipt.PAY_KS:
#                         KsOrderReportRecord.ks_report(instance)
#                 except Exception as e:
#                     logger.error(e)
