from celery import shared_task
import logging
from xiaohongshu.models import XhsGoodsConfig, XhsVoucherCodeRecord, XhsPoi

log = logging.getLogger(__name__)


@shared_task
def session_push_to_xhs():
    return XhsGoodsConfig.session_push_to_xhs()


@shared_task
def xhs_auto_verify_code():
    return XhsVoucherCodeRecord.xhs_auto_verify_code()


@shared_task
def xhs_check_approve_task():
    return XhsGoodsConfig.check_approve_task()


@shared_task
def xhs_get_poi_list():
    return XhsPoi.get_poi_list()
