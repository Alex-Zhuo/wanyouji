from celery import shared_task
import logging
from caiyicloud.models import CyOrder, CySession, CyShowEvent, PromoteActivity

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
def pull_all_event_task(log_title: str):
    return CyShowEvent.pull_all_event_task(log_title)


@shared_task
def pull_new_event_task(log_title: str):
    return CyShowEvent.pull_new_event_task(log_title)


@shared_task
def notify_create_show_task(event_ids: list, log_title: str):
    # 异步创建项目和场次
    return CyShowEvent.notify_create_show_task(event_ids, log_title)


@shared_task
def notify_update_record(event_id: str):
    # 更新项目
    return CyShowEvent.notify_update_record(event_id)


@shared_task
def notify_update_session(event_change_type: int, cy_sessions_list: list):
    # 更新场次
    return CyShowEvent.notify_update_session(event_change_type, cy_sessions_list)


@shared_task
def notify_update_ticket_type(event_change_type: int, price_ids: list):
    # 更新场次
    return CyShowEvent.notify_update_ticket_type(event_change_type, price_ids)


@shared_task
def promote_auto_end_task():
    # 营销活动设为已结束
    return PromoteActivity.do_auto_end_task()


@shared_task
def auto_check_order_out_task():
    # 定时拉取二维码
    return CyOrder.auto_check_order_out_task()
