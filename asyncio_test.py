import aiohttp
import asyncio
import time
import aioredis
import contextlib
import json


@contextlib.asynccontextmanager
async def get_pika_redis():
    url = 'redis://172.16.0.10:9221/1'
    redis = await aioredis.from_url(
        url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()


async def fetch(session, url):
    start_time = time.time()
    data = {"pay_type": 7, "multiply": 1, "amount": 22, "actual_amount": 22, "mobile": "15577150426",
            "session_id": "e5a1942ff1d44fc3be86d3748a96c8d6", "ticket_list": [{"level_id": 192, "multiply": 1}],
            "channel_type": 1}
    headers = dict()
    async with session.post(url, json=data, headers=headers) as response:
        ret = await response.text()
        status = response.status
        end_time = time.time()
        elapsed_ms = int((end_time - start_time) * 1000)  # 计算时间差ms
        return ret, status, elapsed_ms


async def main():
    async with aiohttp.ClientSession() as session:
        async with get_pika_redis() as redis:
            num = 2000
            ms_total = 0
            success = 0
            fail = 0
            max_ms = 0
            min_ms = 0
            tasks = []
            for i in list(range(0, num)):
                token = await redis.lindex('test_token', i)
                # tasks.append(fetch(session, f"http://127.0.0.1:8168/api/users/new_info/?Actoken={token}"))
                tasks.append(fetch(session, f"http://172.16.0.12/api/show/order/noseat_order_new/?Actoken={token}"))
            responses = await asyncio.gather(*tasks)
            for ret in responses:
                status = ret[1]
                data = ret[0]
                st = False
                try:
                    data = json.loads(data)
                    if 200 <= status < 300 and data.get('order_id'):
                        st = True
                except Exception as e:
                    print(data)
                elapsed_ms = ret[2]
                ms_total += elapsed_ms
                # print('{},{}'.format(elapsed_ms, st))
                if st:
                    success += 1
                else:
                    fail += 1
                if elapsed_ms > max_ms:
                    max_ms = elapsed_ms
                if min_ms == 0 or min_ms > elapsed_ms:
                    min_ms = elapsed_ms
            avg = ms_total / num
            print(f'平均响应时间:{avg}ms,最长响应时间:{max_ms}ms,最短响应时间:{min_ms}ms,成功响应:{success},失败请求:{fail}')


asyncio.run(main())
