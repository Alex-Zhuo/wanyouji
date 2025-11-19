# coding=utf-8
"""
抽奖逻辑工具函数
"""
import random
import logging
from typing import List, Optional
from blind_box.models import Prize

log = logging.getLogger(__name__)


def weighted_random_choice(items: List[dict]) -> (Optional[None, Prize], Optional[None, int]):
    """
    根据权重随机选择
    items: [{'item': obj, 'weight': int}, ...]
    """
    if not items:
        return None, None

    total_weight = sum(item['weight'] for item in items)
    if total_weight == 0:
        return None, None
    prize_index = 0
    rand = random.uniform(0, total_weight)
    current = 0

    for item in items:
        current += item['weight']
        if rand <= current:
            return item['item'], prize_index
        prize_index += 1

    return None, None

#
# @transaction.atomic
# def draw_wheel_prize(wheel_activity: WheelActivity, user) -> Optional[BlindBoxWinningRecord]:
#     """
#     转盘抽奖
#     转盘片区附表中库存不为0的奖品权重数总和
#     """
#     # 获取启用的片区
#     sections = wheel_activity.sections.filter(is_enabled=True).select_related('prize')
#
#     # 构建候选奖品列表（库存不为0的奖品）
#     candidates = []
#     for section in sections:
#         prize = section.prize
#         if prize and prize.status == Prize.STATUS_ON:
#             # 检查库存（从redis获取）
#             stock = prsc.get_stock(prize.id)
#             if stock and int(stock) > 0:
#                 candidates.append({
#                     'item': prize,
#                     'weight': section.weight,
#                     'section': section
#                 })
#
#     if not candidates:
#         log.warning(f"转盘活动 {wheel_activity.id} 没有可抽中的奖品")
#         return None
#
#     # 根据权重随机选择
#     selected = weighted_random_choice(candidates)
#     if not selected:
#         return None
#
#     prize = selected
#     section = next(c['section'] for c in candidates if c['item'] == prize)
#
#     # 减少库存（使用incr方法，ceiling=0表示减后必须>=0）
#     success, new_stock = prsc.incr(prize.id, -1, ceiling=0)
#     if not success:
#         log.warning(f"奖品 {prize.id} 库存不足")
#         return None
#     prsc.record_update_ts(prize.id)
#
#     # 创建中奖记录
#     winning_record = WinningRecord.objects.create(
#         user=user,
#         mobile=user.mobile if hasattr(user, 'mobile') else '',
#         prize=prize,
#         source_type=prize.source_type,
#         instruction=prize.instruction,
#         status=ST_PENDING_RECEIVE if prize.source_type in [SR_TICKET, SR_CODE] else (
#             ST_PENDING_SHIP if prize.source_type == SR_GOOD else ST_COMPLETED
#         ),
#         source=WinningRecord.SOURCE_WHEEL,
#         wheel_activity=wheel_activity,
#         winning_at=timezone.now()
#     )
#
#     # 如果是消费券类型，自动进入"我的消费券"并设置为已完成
#     if prize.source_type == SR_COUPON:
#         # TODO: 这里需要调用消费券模块的接口，将消费券添加到用户账户
#         # from coupon.models import UserCouponRecord, Coupon
#         # 需要根据prize关联的消费券信息创建UserCouponRecord
#         winning_record.set_completed()
#
#     return winning_record
#
