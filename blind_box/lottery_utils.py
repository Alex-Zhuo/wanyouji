# coding=utf-8
"""
抽奖逻辑工具函数
"""
import random
import logging
from typing import List, Optional
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from blind_box.models import (
    Prize, WheelActivity, WheelSection, BlindBox, BlindBoxWinningRecord, BlindBoxWinningRecord,
    SR_COUPON, SR_TICKET, SR_CODE, SR_GOOD,
)
# 导入中奖记录状态常量
ST_PENDING_RECEIVE = BlindBoxWinningRecord.ST_PENDING_RECEIVE
ST_PENDING_SHIP = BlindBoxWinningRecord.ST_PENDING_SHIP
ST_COMPLETED = BlindBoxWinningRecord.ST_COMPLETED
from blind_box.stock_updater import prsc

log = logging.getLogger(__name__)


def weighted_random_choice(items: List[dict]) -> Optional[dict]:
    """
    根据权重随机选择
    items: [{'item': obj, 'weight': int}, ...]
    """
    if not items:
        return None

    total_weight = sum(item['weight'] for item in items)
    if total_weight == 0:
        return None

    rand = random.uniform(0, total_weight)
    current = 0

    for item in items:
        current += item['weight']
        if rand <= current:
            return item['item']

    return items[-1]['item']


@transaction.atomic
def draw_wheel_prize(wheel_activity: WheelActivity, user) -> Optional[BlindBoxWinningRecord]:
    """
    转盘抽奖
    转盘片区附表中库存不为0的奖品权重数总和
    """
    # 获取启用的片区
    sections = wheel_activity.sections.filter(is_enabled=True).select_related('prize')

    # 构建候选奖品列表（库存不为0的奖品）
    candidates = []
    for section in sections:
        prize = section.prize
        if prize and prize.status == Prize.STATUS_ON:
            # 检查库存（从redis获取）
            stock = prsc.get_stock(prize.id)
            if stock and int(stock) > 0:
                candidates.append({
                    'item': prize,
                    'weight': section.weight,
                    'section': section
                })

    if not candidates:
        log.warning(f"转盘活动 {wheel_activity.id} 没有可抽中的奖品")
        return None

    # 根据权重随机选择
    selected = weighted_random_choice(candidates)
    if not selected:
        return None

    prize = selected
    section = next(c['section'] for c in candidates if c['item'] == prize)

    # 减少库存（使用incr方法，ceiling=0表示减后必须>=0）
    success, new_stock = prsc.incr(prize.id, -1, ceiling=0)
    if not success:
        log.warning(f"奖品 {prize.id} 库存不足")
        return None
    prsc.record_update_ts(prize.id)

    # 创建中奖记录
    winning_record = WinningRecord.objects.create(
        user=user,
        mobile=user.mobile if hasattr(user, 'mobile') else '',
        prize=prize,
        source_type=prize.source_type,
        instruction=prize.instruction,
        status=ST_PENDING_RECEIVE if prize.source_type in [SR_TICKET, SR_CODE] else (
            ST_PENDING_SHIP if prize.source_type == SR_GOOD else ST_COMPLETED
        ),
        source=WinningRecord.SOURCE_WHEEL,
        wheel_activity=wheel_activity,
        winning_at=timezone.now()
    )

    # 如果是消费券类型，自动进入"我的消费券"并设置为已完成
    if prize.source_type == SR_COUPON:
        # TODO: 这里需要调用消费券模块的接口，将消费券添加到用户账户
        # from coupon.models import UserCouponRecord, Coupon
        # 需要根据prize关联的消费券信息创建UserCouponRecord
        winning_record.set_completed()

    return winning_record


@transaction.atomic
def draw_blind_box_prizes(blind_box: BlindBox, user) -> List[BlindBoxWinningRecord]:
    """
    盲盒抽奖
    每个格抽出的奖品不重复，下一格抽取时需要去掉上一格的奖品
    
    奖品权重数×类型倍数/去掉本次开盒已抽出的奖品后，剩余库存不为0的奖品权重数总和
    
    并发安全处理：
    1. 使用事务保证原子性
    2. 记录所有已扣减的库存，失败时回滚
    3. 库存扣减失败时循环重试，直到成功或没有候选奖品
    """
    winning_records = []
    grids_num = blind_box.grids_num
    drawn_prize_ids = []  # 本次开盒已抽出的奖品ID列表
    deducted_stocks = []  # 已扣减的库存记录，格式: [(prize_id, 数量), ...]
    
    try:
        # 检查奖品池库存
        available_prizes = Prize.objects.filter(status=Prize.STATUS_ON)
        available_count = 0
        for prize in available_prizes:
            stock = prsc.get_stock(prize.id)
            if stock and int(stock) > 0:
                available_count += 1

        if available_count < grids_num:
            raise Exception("奖品库存不足，请稍后再试！")

        for i in range(grids_num):
            # 获取可抽取的奖品（排除本次开盒已抽出的奖品）
            # 只考虑库存不为0的奖品
            candidates = []
            for prize in Prize.objects.filter(status=Prize.STATUS_ON).exclude(id__in=drawn_prize_ids):
                # 检查库存（从redis实时获取）
                stock = prsc.get_stock(prize.id)
                if not stock or int(stock) <= 0:
                    continue

                # 计算权重：奖品权重数 × 类型倍数
                # 普通款：权重 = 奖品权重数
                # 稀有款：权重 = 奖品权重数 × 稀有款权重倍数
                # 隐藏款：权重 = 奖品权重数 × 隐藏款权重倍数
                base_weight = prize.weight
                if prize.rare_type == Prize.RA_RARE:
                    weight = base_weight * blind_box.rare_weight_multiple
                elif prize.rare_type == Prize.RA_HIDDEN:
                    weight = base_weight * blind_box.hidden_weight_multiple
                else:
                    weight = base_weight

                # 权重必须大于0才能参与抽奖
                if weight > 0:
                    candidates.append({
                        'item': prize,
                        'weight': weight
                    })

            if not candidates:
                log.error(f"盲盒 {blind_box.id} 第 {i + 1} 格没有可抽中的奖品")
                raise Exception(f"奖品库存不足，无法完成第 {i + 1} 格抽奖")

            # 循环尝试抽取，直到成功或没有候选奖品
            selected_prize = None
            success = False
            max_retries = len(candidates)  # 最多重试次数等于候选奖品数量
            retry_count = 0
            
            while not success and retry_count < max_retries:
                # 根据权重随机选择
                # 概率计算公式：奖品权重数×类型倍数 / 去掉本次开盒已抽出的奖品后，剩余库存不为0的奖品权重数总和
                # weighted_random_choice函数内部会计算总权重作为分母
                selected_prize = weighted_random_choice(candidates)
                if not selected_prize:
                    raise Exception(f"抽奖失败，无法完成第 {i + 1} 格抽奖")

                # 减少库存（使用incr方法，ceiling=0表示减后必须>=0，原子操作保证并发安全）
                success, new_stock = prsc.incr(selected_prize.id, -1, ceiling=0)
                if not success:
                    # 如果减库存失败（可能被其他请求并发减掉了），从候选列表中移除该奖品，继续重试
                    log.warning(f"奖品 {selected_prize.id} 库存不足，尝试重新抽取（第 {retry_count + 1} 次重试）")
                    candidates = [c for c in candidates if c['item'].id != selected_prize.id]
                    if not candidates:
                        raise Exception(f"奖品库存不足，无法完成第 {i + 1} 格抽奖")
                    retry_count += 1
                else:
                    # 库存扣减成功，记录已扣减的库存
                    deducted_stocks.append(selected_prize.id)
                    prsc.record_update_ts(selected_prize.id)

            if not success:
                raise Exception(f"奖品库存不足，无法完成第 {i + 1} 格抽奖")

            # 添加到已抽中列表
            drawn_prize_ids.append(selected_prize.id)

            # 创建中奖记录
            winning_record = WinningRecord.objects.create(
                user=user,
                mobile=user.mobile if hasattr(user, 'mobile') else '',
                prize=selected_prize,
                source_type=selected_prize.source_type,
                instruction=selected_prize.instruction,
                status=ST_PENDING_RECEIVE if selected_prize.source_type in [SR_TICKET, SR_CODE] else (
                    ST_PENDING_SHIP if selected_prize.source_type == SR_GOOD else ST_COMPLETED
                ),
                source=WinningRecord.SOURCE_BLIND,
                blind_box=blind_box,
                winning_at=timezone.now()
            )

            # 如果是消费券类型，自动进入"我的消费券"并设置为已完成
            if selected_prize.source_type == SR_COUPON:
                # TODO: 这里需要调用消费券模块的接口
                winning_record.set_completed()

            winning_records.append(winning_record)

        # 确保抽取的奖品数量等于格子数
        if len(winning_records) != grids_num:
            log.error(f"盲盒 {blind_box.id} 抽奖异常：期望 {grids_num} 个奖品，实际 {len(winning_records)} 个")
            raise Exception("抽奖失败，请稍后重试")

        return winning_records
        
    except Exception as e:
        # 如果抽奖过程中出现任何异常，回滚所有已扣减的库存
        if deducted_stocks:
            log.warning(f"盲盒 {blind_box.id} 抽奖失败，开始回滚已扣减的库存，共 {len(deducted_stocks)} 个奖品")
            for prize_id in deducted_stocks:
                try:
                    # 回滚库存（加回库存）
                    prsc.incr(prize_id, 1, ceiling=Ellipsis, disable_record_update_ts=True)
                    prsc.record_update_ts(prize_id)
                    log.info(f"已回滚奖品 {prize_id} 的库存")
                except Exception as rollback_error:
                    log.error(f"回滚奖品 {prize_id} 库存失败: {rollback_error}")
        
        # 删除已创建的中奖记录（如果事务回滚，这些记录会自动删除，但为了保险起见，我们手动删除）
        if winning_records:
            try:
                for record in winning_records:
                    record.delete()
            except Exception as delete_error:
                log.error(f"删除中奖记录失败: {delete_error}")
        
        # 重新抛出异常
        raise
