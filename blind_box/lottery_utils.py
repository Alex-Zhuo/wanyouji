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
