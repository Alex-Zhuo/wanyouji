# coding=utf-8
"""
抽奖逻辑工具函数
"""
import random
import logging
from typing import List, Optional

log = logging.getLogger(__name__)


def calculate_probabilities_prize(items: List[dict]):
    """
    计算每个奖品的理论概率

    Args:
        prizes: 字典，key为奖品名称，value为权重值

    Returns:
        字典，key为奖品名称，value为概率
    """
    total_weight = sum(item['weight'] for item in items)
    probabilities = {}

    for item in items:
        prize = item['item']
        probabilities[prize.title] = item['weight'] / total_weight

    return probabilities


def weighted_random_choice(items: List[dict]):
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


def weighted_random_draw_manual(prizes):
    """
    手动实现的加权随机算法（不依赖random.choices）

    Args:
        prizes: 字典，key为奖品名称，value为权重值

    Returns:
        抽中的奖品名称
    """
    if not prizes:
        raise ValueError("奖品列表不能为空")

    # 计算总权重
    total_weight = sum(prizes.values())

    # 生成一个0到总权重之间的随机数
    random_num = random.uniform(0, total_weight)

    # 遍历奖品，找到随机数落在的区间
    current_weight = 0
    for prize, weight in prizes.items():
        current_weight += weight
        if random_num <= current_weight:
            return prize

    # 理论上不会执行到这里，但为了安全返回最后一个奖品
    return list(prizes.keys())[-1]


def calculate_probabilities(prizes):
    """
    计算每个奖品的理论概率

    Args:
        prizes: 字典，key为奖品名称，value为权重值

    Returns:
        字典，key为奖品名称，value为概率
    """
    total_weight = sum(prizes.values())
    probabilities = {}

    for prize, weight in prizes.items():
        probabilities[prize] = weight / total_weight

    return probabilities


# 测试代码
if __name__ == "__main__":
    # 定义奖品和权重
    prizes = {
        "A奖品": 1000,
        "B奖品": 1000,
        "C奖品": 1000,
        "D奖品": 20,
        "E奖品": 5,
        "F奖品": 2000
    }

    # 计算理论概率
    probabilities = calculate_probabilities(prizes)
    print("各奖品的理论概率：")
    for prize, prob in probabilities.items():
        print(f"{prize}: {prob:.4f} ({prob * 100:.2f}%)")

    print("\n使用random.choices方法进行10000次抽奖测试：")
    # 进行多次抽奖测试
    test_count = 10000
    results = {}

    # 测试手动实现的方法
    results_manual = {}

    for _ in range(test_count):
        selected = weighted_random_draw_manual(prizes)
        results_manual[selected] = results_manual.get(selected, 0) + 1

    # 输出测试结果
    for prize, count in results_manual.items():
        actual_prob = count / test_count
        theoretical_prob = probabilities[prize]
        print(f"{prize}: 出现{count}次, 实际概率: {actual_prob:.4f}, 理论概率: {theoretical_prob:.4f}")
