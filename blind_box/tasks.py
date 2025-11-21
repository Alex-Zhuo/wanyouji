from celery import shared_task
import logging
from django.utils import timezone
from datetime import timedelta
from blind_box.models import BlindBox, Prize, BlindBoxOrder, BlindBoxWinningRecord, WheelWinningRecord

log = logging.getLogger(__name__)


@shared_task
def prize_update_stock_from_redis_task():
    # 奖品库存更新到数据库
    Prize.prize_update_stock_from_redis()


@shared_task
def blind_box_update_stock_from_redis_task():
    # 盲盒库存更新到数据库
    BlindBox.blind_box_update_stock_from_redis()


@shared_task
def blind_box_order_auto_cancel_task():
    # 盲盒订单自动取消返回库存
    BlindBoxOrder.auto_cancel_task()


@shared_task
def auto_confirm_prize_task():
    """
    中奖记录发货后7天自动确认收货任务
    """
    BlindBoxWinningRecord.auto_finished()
    WheelWinningRecord.auto_finished()
