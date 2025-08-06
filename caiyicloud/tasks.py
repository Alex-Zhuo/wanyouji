from celery import shared_task
import logging
from caiyicloud.models import CyOrder, CySession, CyShowEvent

log = logging.getLogger(__name__)


@shared_task
def async_confirm_order(ticket_order_id: int):
    # 异步确认订单
    return CyOrder.async_confirm_order(ticket_order_id)


@shared_task
def confirm_order_task():
    # 异步确认订单失败，定时任务重试
    return CyOrder.confirm_order_task()


@shared_task
def cy_update_stock_task():
    return CySession.cy_update_stock_task()


@shared_task
def notify_create_show_task(event_id: str):
    # 异步创建项目和场次
    return CyShowEvent.notify_create_show_task(event_id)
