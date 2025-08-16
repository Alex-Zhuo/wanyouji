import asyncio
import aiohttp
import time
import uuid
import threading
from aiohttp import TCPConnector, ClientTimeout
from collections import deque

task_start_times = deque()
completed_tasks = 0


def generate_payload():
    request_id = str(uuid.uuid4())
    return {
        "request_id": request_id,
        "param1": "xxx",
        "param2": "xxx",
        "param3": "xxx"
    }


async def fetch(session: aiohttp.ClientSession, url: str, payload: dict):
    try:
        # async with session.post(url, data=payload, timeout=ClientTimeout(total=1200)) as response:
        async with session.get(url, timeout=ClientTimeout(total=1200)) as response:
            return await response.json()
    except Exception as e:
        print(f"请求异常: {e}")
        return {}


async def check_status(session: aiohttp.ClientSession, status_url: str, request_id: str, max_retries=240):
    retry_count = 0
    while retry_count < max_retries:
        try:
            form_data = {'request_id': request_id}
            async with session.post(status_url, data=form_data, timeout=ClientTimeout(total=30)) as response:
                status = await response.json()
                message = status.get("message", "")
                if "xxx" in message:
                    print(f"任务 {request_id} 成功，结果: {message}")
                    return status
                elif status.get("status") == "failure":
                    print(f"任务 {request_id} 失败.")
                    return status
                else:
                    print(f"任务 {request_id} 处理中，继续等待...")
            await asyncio.sleep(5)
            retry_count += 1
        except aiohttp.ServerDisconnectedError:
            print(f"服务器断开连接，正在重试 ({retry_count + 1}/{max_retries})")
            await asyncio.sleep(5)
            retry_count += 1
        except Exception as e:
            print(f"检查状态异常: {e}")
            await asyncio.sleep(5)
            retry_count += 1
    print(f"任务 {request_id} 超时未完成.")
    return {}


async def worker(name: int, url: str, status_url: str, sem: asyncio.Semaphore, session: aiohttp.ClientSession):
    global completed_tasks
    async with sem:
        payload = generate_payload()
        request_id = payload["request_id"]
        start_time = time.time()

        task_start_times.append(start_time)

        result = await fetch(session, url, payload)
        if result.get("status") == "success":
            print(f"任务 {name} 提交成功，request_id: {request_id}")
            # status_result = await check_status(session, status_url, request_id)
            elapsed_time = time.time() - start_time
            print(f"任务 {name} 完成，耗时 {elapsed_time:.2f} 秒，状态: ")
        else:
            print(f"任务 {name} 提交失败，错误: {result.get('message')}")

        completed_tasks += 1  # 完成任务计数
        return result


async def run_load_test(url: str, status_url: str, total_requests: int, max_concurrency: int):
    timeout = ClientTimeout(total=1200)
    connector = TCPConnector(limit_per_host=200)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        sem = asyncio.Semaphore(max_concurrency)
        tasks = [asyncio.create_task(worker(i, url, status_url, sem, session)) for i in range(total_requests)]
        return await asyncio.gather(*tasks)


def calculate_tps():
    global task_start_times, completed_tasks
    while True:
        time.sleep(60)
        current_time = time.time()
        while task_start_times and current_time - task_start_times[0] > 60:
            task_start_times.popleft()

        tps = len(task_start_times)
        print(f"当前TPS: {tps} tasks/min")
        print(f"总完成任务数: {completed_tasks}")


if __name__ == '__main__':
    #server_ip = "your server ip"
    #url = server_ip + "/xxx/submit"
    url = 'http://172.16.0.12/api/users/new_info/?Actoken=7acfd418eeb0bfb9f072ec8d29c6bc491_1755329817'
    # status_url = server_ip + "/xxx/status"
    status_url = ''
    total_requests = 10000
    max_concurrency = 1000

    print(f"开始压力测试: 总请求数 {total_requests}, 最大并发 {max_concurrency}")
    start_time = time.time()

    tps_calculator = threading.Thread(target=calculate_tps)
    tps_calculator.daemon = True
    tps_calculator.start()

    asyncio.run(run_load_test(url, status_url, total_requests, max_concurrency))
    total_time = time.time() - start_time
    print(f"压力测试完成: 总耗时 {total_time:.2f} 秒")