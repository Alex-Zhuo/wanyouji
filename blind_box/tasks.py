from celery import shared_task
import logging
from django.utils import timezone
from datetime import timedelta
from blind_box.models import BlindBox, Prize

log = logging.getLogger(__name__)


@shared_task
def prize_update_stock_from_redis_task():
    # 奖品库存更新到数据库
    Prize.prize_update_stock_from_redis()


@shared_task
def blind_box_update_stock_from_redis_task():
    # 盲盒库存更新到数据库
    BlindBox.blind_box_update_stock_from_redis()

# @shared_task
# def auto_confirm_receipt_task():
#     """
#     自动确认收货任务
#     发货后7天自动确认收货
#     """
#     # 查找发货时间超过7天且状态为待收货的记录
#     seven_days_ago = timezone.now() - timedelta(days=7)
#     records = WinningRecord.objects.filter(
#         source_type=Prize.SR_GOOD,
#         status=WinningRecord.ST_PENDING_RECEIPT,
#         ship_at__lte=seven_days_ago
#     )
#
#     count = 0
#     for record in records:
#         record.set_completed()
#         count += 1
#
#     log.info(f"自动确认收货任务完成，共处理 {count} 条记录")
#     return count
