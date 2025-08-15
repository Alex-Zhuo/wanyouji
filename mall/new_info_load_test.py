#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mall new_info 接口 10000并发压力测试脚本
专门针对 /api/users/new_info/ 接口进行高并发压力测试
"""

import time
import json
import random
import threading
import statistics
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import argparse
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('new_info_load_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """测试结果数据类"""
    url: str
    method: str
    status_code: int
    response_time: float
    success: bool
    error_message: str = ""
    timestamp: float = 0.0
    user_id: str = ""
    share_code: str = ""


@dataclass
class TestSummary:
    """测试汇总数据类"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    success_rate: float
    error_distribution: Dict[str, int]
    response_time_distribution: Dict[str, int]


class NewInfoLoadTester:
    """new_info接口专用负载测试器"""
    
    def __init__(self, base_url: str, auth_tokens: List[str] = None):
        """
        初始化负载测试器
        
        Args:
            base_url: API基础URL
            auth_tokens: 认证token列表，用于模拟不同用户
        """
        self.base_url = base_url.rstrip('/')
        self.auth_tokens = auth_tokens or []
        self.sessions: List[requests.Session] = []
        self.results: List[TestResult] = []
        self.lock = threading.Lock()
        
        # 初始化多个session，每个对应一个token
        for token in self.auth_tokens:
            session = requests.Session()
            session.headers.update({
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'LoadTest/1.0'
            })
            self.sessions.append(session)
        
        # 如果没有提供token，创建一个默认session
        if not self.auth_tokens:
            default_session = requests.Session()
            default_session.headers.update({
                'Content-Type': 'application/json',
                'User-Agent': 'LoadTest/1.0'
            })
            self.sessions.append(default_session)
    
    def _get_random_session(self) -> requests.Session:
        """获取随机的session"""
        return random.choice(self.sessions)
    
    def _generate_share_codes(self) -> List[str]:
        """生成测试用的分享码"""
        # 生成一些模拟的分享码
        share_codes = [
            "ABC123", "DEF456", "GHI789", "JKL012", "MNO345",
            "PQR678", "STU901", "VWX234", "YZA567", "BCD890",
            "EFG123", "HIJ456", "KLM789", "NOP012", "QRS345",
            "TUV678", "WXY901", "ZAB234", "CDE567", "FGH890"
        ]
        return share_codes
    
    def _make_request(self, user_id: str = None, share_code: str = None) -> TestResult:
        """
        发送单个new_info请求并记录结果
        
        Args:
            user_id: 用户ID（用于标识）
            share_code: 可选的分享码参数
            
        Returns:
            TestResult: 测试结果
        """
        endpoint = '/users/new_info/'
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        # 构建请求参数
        params = {}
        if share_code:
            params['share_code'] = share_code
        
        try:
            # 随机选择一个session
            session = self._get_random_session()
            
            # 发送GET请求
            response = session.get(url, params=params, timeout=30)
            response_time = time.time() - start_time
            
            result = TestResult(
                url=url,
                method='GET',
                status_code=response.status_code,
                response_time=response_time,
                success=200 <= response.status_code < 300,
                timestamp=start_time,
                user_id=user_id or "unknown",
                share_code=share_code or ""
            )
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            result = TestResult(
                url=url,
                method='GET',
                status_code=0,
                response_time=response_time,
                success=False,
                error_message=str(e),
                timestamp=start_time,
                user_id=user_id or "unknown",
                share_code=share_code or ""
            )
        
        return result
    
    def _record_result(self, result: TestResult):
        """记录测试结果（线程安全）"""
        with self.lock:
            self.results.append(result)
    
    def concurrent_test(self, concurrent_users: int = 10000, 
                       total_requests: int = 50000,
                       share_code_ratio: float = 0.3) -> TestSummary:
        """
        并发测试 - 支持10000并发用户
        
        Args:
            concurrent_users: 并发用户数
            total_requests: 总请求数
            share_code_ratio: 使用分享码的请求比例
            
        Returns:
            TestSummary: 测试汇总
        """
        logger.info(f"🚀 开始10000并发测试: new_info接口")
        logger.info(f"并发用户数: {concurrent_users:,}")
        logger.info(f"总请求数: {total_requests:,}")
        logger.info(f"分享码使用比例: {share_code_ratio:.1%}")
        
        start_time = time.time()
        share_codes = self._generate_share_codes()
        
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = []
            
            for i in range(total_requests):
                # 决定是否使用分享码
                use_share_code = random.random() < share_code_ratio
                share_code = random.choice(share_codes) if use_share_code else None
                
                # 生成用户ID
                user_id = f"user_{i % 1000:04d}"
                
                future = executor.submit(
                    self._make_request, user_id, share_code
                )
                futures.append(future)
                
                # 每1000个请求显示进度
                if (i + 1) % 1000 == 0:
                    logger.info(f"已提交 {i + 1:,} 个请求...")
            
            logger.info("所有请求已提交，等待完成...")
            
            # 收集结果
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                self._record_result(result)
                completed += 1
                
                # 每1000个完成显示进度
                if completed % 1000 == 0:
                    logger.info(f"已完成 {completed:,} 个请求...")
        
        total_time = time.time() - start_time
        
        logger.info(f"✅ 测试完成！总耗时: {total_time:.2f}秒")
        return self._calculate_summary(total_time)
    
    def stress_test(self, initial_users: int = 1000, max_users: int = 10000,
                   step_users: int = 1000, step_duration: int = 60,
                   share_code_ratio: float = 0.3) -> List[TestSummary]:
        """
        压力测试 - 逐步增加负载到10000并发
        
        Args:
            initial_users: 初始并发用户数
            max_users: 最大并发用户数
            step_users: 每步增加的并发用户数
            step_duration: 每步持续时间（秒）
            share_code_ratio: 使用分享码的请求比例
            
        Returns:
            List[TestSummary]: 每步的测试汇总
        """
        logger.info(f"🔥 开始压力测试: 逐步增加到{max_users:,}并发用户")
        
        summaries = []
        current_users = initial_users
        
        while current_users <= max_users:
            logger.info(f"当前并发用户数: {current_users:,}")
            
            # 清空之前的结果
            self.results.clear()
            
            # 执行当前并发级别的测试
            start_time = time.time()
            self.concurrent_test(current_users, current_users * 2, share_code_ratio)
            
            # 等待指定时间
            elapsed = time.time() - start_time
            if elapsed < step_duration:
                time.sleep(step_duration - elapsed)
            
            # 计算当前步骤的汇总
            summary = self._calculate_summary(step_duration)
            summaries.append(summary)
            
            # 检查是否达到性能阈值
            if summary.success_rate < 0.95 or summary.avg_response_time > 3.0:
                logger.warning(f"⚠️ 性能阈值被触发，停止增加负载")
                logger.warning(f"成功率: {summary.success_rate:.2%}, 平均响应时间: {summary.avg_response_time:.3f}秒")
                break
            
            current_users += step_users
        
        return summaries
    
    def spike_test(self, spike_users: int = 10000, duration_seconds: int = 30,
                   share_code_ratio: float = 0.3) -> TestSummary:
        """
        峰值测试 - 瞬间达到10000并发
        
        Args:
            spike_users: 峰值并发用户数
            duration_seconds: 峰值持续时间（秒）
            share_code_ratio: 使用分享码的请求比例
            
        Returns:
            TestSummary: 测试汇总
        """
        logger.info(f"⚡ 开始峰值测试: 瞬间达到{spike_users:,}并发用户")
        logger.info(f"峰值持续时间: {duration_seconds}秒")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        with ThreadPoolExecutor(max_workers=spike_users) as executor:
            futures = []
            
            # 瞬间提交所有请求
            for i in range(spike_users):
                use_share_code = random.random() < share_code_ratio
                share_code = random.choice(self._generate_share_codes()) if use_share_code else None
                user_id = f"spike_user_{i:05d}"
                
                future = executor.submit(
                    self._make_request, user_id, share_code
                )
                futures.append(future)
            
            logger.info(f"已提交 {spike_users:,} 个峰值请求，等待完成...")
            
            # 等待所有请求完成或超时
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                self._record_result(result)
                completed += 1
                
                # 检查是否超时
                if time.time() > end_time:
                    logger.warning("⚠️ 峰值测试超时，强制结束")
                    break
                
                # 每1000个完成显示进度
                if completed % 1000 == 0:
                    logger.info(f"已完成 {completed:,} 个峰值请求...")
        
        total_time = time.time() - start_time
        return self._calculate_summary(total_time)
    
    def _calculate_summary(self, total_time: float) -> TestSummary:
        """计算测试汇总数据"""
        if not self.results:
            return TestSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, {}, {})
        
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        
        response_times = [r.response_time for r in self.results]
        response_times.sort()
        
        total_requests = len(self.results)
        successful_requests = len(successful)
        failed_requests = len(failed)
        
        avg_response_time = statistics.mean(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        
        # 计算百分位数
        p95_index = int(len(response_times) * 0.95)
        p99_index = int(len(response_times) * 0.99)
        
        p95_response_time = response_times[p95_index] if p95_index < len(response_times) else 0
        p99_response_time = response_times[p99_index] if p99_index < len(response_times) else 0
        
        requests_per_second = total_requests / total_time if total_time > 0 else 0
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        
        # 错误分布统计
        error_distribution = {}
        for result in failed:
            error_type = f"HTTP_{result.status_code}" if result.status_code > 0 else "Network_Error"
            error_distribution[error_type] = error_distribution.get(error_type, 0) + 1
        
        # 响应时间分布统计
        response_time_distribution = {
            "0-100ms": len([r for r in response_times if r < 0.1]),
            "100-500ms": len([r for r in response_times if 0.1 <= r < 0.5]),
            "500ms-1s": len([r for r in response_times if 0.5 <= r < 1.0]),
            "1-3s": len([r for r in response_times if 1.0 <= r < 3.0]),
            "3-5s": len([r for r in response_times if 3.0 <= r < 5.0]),
            "5s+": len([r for r in response_times if r >= 5.0])
        }
        
        return TestSummary(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            success_rate=success_rate,
            error_distribution=error_distribution,
            response_time_distribution=response_time_distribution
        )
    
    def print_summary(self, summary: TestSummary, test_name: str = "测试"):
        """打印测试汇总信息"""
        print(f"\n{'='*60}")
        print(f"{test_name} 结果汇总")
        print(f"{'='*60}")
        print(f"总请求数: {summary.total_requests:,}")
        print(f"成功请求: {summary.successful_requests:,}")
        print(f"失败请求: {summary.failed_requests:,}")
        print(f"成功率: {summary.success_rate:.2%}")
        print(f"平均响应时间: {summary.avg_response_time:.3f}秒")
        print(f"最小响应时间: {summary.min_response_time:.3f}秒")
        print(f"最大响应时间: {summary.max_response_time:.3f}秒")
        print(f"95%响应时间: {summary.p95_response_time:.3f}秒")
        print(f"99%响应时间: {summary.p99_response_time:.3f}秒")
        print(f"每秒请求数: {summary.requests_per_second:.2f}")
        
        if summary.error_distribution:
            print(f"\n错误分布:")
            for error_type, count in summary.error_distribution.items():
                print(f"  {error_type}: {count}")
        
        if summary.response_time_distribution:
            print(f"\n响应时间分布:")
            for time_range, count in summary.response_time_distribution.items():
                print(f"  {time_range}: {count}")
        
        print(f"{'='*60}")
    
    def export_results(self, filename: str = None):
        """导出测试结果到JSON文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"new_info_load_test_results_{timestamp}.json"
        
        export_data = {
            'test_info': {
                'interface': 'new_info',
                'base_url': self.base_url,
                'timestamp': datetime.now().isoformat(),
                'total_results': len(self.results)
            },
            'results': [
                {
                    'url': r.url,
                    'method': r.method,
                    'status_code': r.status_code,
                    'response_time': r.response_time,
                    'success': r.success,
                    'error_message': r.error_message,
                    'timestamp': r.timestamp,
                    'user_id': r.user_id,
                    'share_code': r.share_code
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"测试结果已导出到: {filename}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Mall new_info接口10000并发压力测试工具')
    parser.add_argument('--url', required=True, help='API基础URL (例如: http://localhost:8000/api)')
    parser.add_argument('--tokens', nargs='+', help='认证token列表，用于模拟不同用户')
    parser.add_argument('--test-type', choices=['concurrent', 'stress', 'spike'], 
                       default='concurrent', help='测试类型')
    parser.add_argument('--users', type=int, default=10000, help='并发用户数')
    parser.add_argument('--requests', type=int, default=50000, help='总请求数')
    parser.add_argument('--share-ratio', type=float, default=0.3, help='分享码使用比例')
    parser.add_argument('--export', action='store_true', help='导出测试结果')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    print(f"🚀 Mall new_info接口压力测试")
    print(f"🔗 API地址: {args.url}")
    print(f"📋 测试类型: {args.test_type}")
    print(f"👥 并发用户数: {args.users:,}")
    print(f"📊 总请求数: {args.requests:,}")
    print(f"🔗 分享码比例: {args.share_ratio:.1%}")
    
    # 创建测试器
    try:
        tester = NewInfoLoadTester(args.url, args.tokens)
        print("✅ 测试器初始化成功")
    except Exception as e:
        print(f"❌ 测试器初始化失败: {e}")
        sys.exit(1)
    
    # 运行测试
    try:
        if args.test_type == 'concurrent':
            result = tester.concurrent_test(
                concurrent_users=args.users,
                total_requests=args.requests,
                share_code_ratio=args.share_ratio
            )
            tester.print_summary(result, f"10000并发测试 - new_info接口")
            
        elif args.test_type == 'stress':
            results = tester.stress_test(
                initial_users=1000,
                max_users=args.users,
                step_users=1000,
                step_duration=60,
                share_code_ratio=args.share_ratio
            )
            
            for i, summary in enumerate(results):
                tester.print_summary(summary, f"压力测试 - 步骤 {i+1}")
                
        elif args.test_type == 'spike':
            result = tester.spike_test(
                spike_users=args.users,
                duration_seconds=30,
                share_code_ratio=args.share_ratio
            )
            tester.print_summary(result, f"峰值测试 - {args.users:,}并发用户")
        
        # 导出结果
        if args.export:
            filename = f"new_info_{args.test_type}_{args.users}users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            tester.export_results(filename)
            print(f"📁 测试结果已导出到: {filename}")
        
        print("\n🎉 测试完成！")
        
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
