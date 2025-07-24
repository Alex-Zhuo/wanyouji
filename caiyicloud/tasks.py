from celery import shared_task
import logging
from caiyicloud.models import CyOrder

log = logging.getLogger(__name__)


@shared_task
def async_confirm_order(ticket_order_id: int):
    # 异步确认订单
    return CyOrder.async_confirm_order(ticket_order_id)


@shared_task
def confirm_order_task():
    # 异步确认订单失败，定时任务重试
    return CyOrder.confirm_order_task()
