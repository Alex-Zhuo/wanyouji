import aiohttp
import asyncio
import time
import aioredis
import contextlib


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
    async with session.get(url) as response:
        ret = await response.text()
        status = response.status
        return ret, status


async def main():
    async with aiohttp.ClientSession() as session:
        async with get_pika_redis() as redis:
            num = 10000
            ms_total = 0
            success = 0
            fail = 0
            max_ms = 0
            min_ms = 0
            for i in list(range(0, num)):
                token = await redis.lindex('test_token', i)
                st = False
                start_time = time.time()
                data, status = await fetch(session, f"http://127.0.0.1:8168/api/users/new_info/?Actoken={token}")
                if 200 <= status < 300:
                    st = True
                end_time = time.time()
                elapsed_ms = int((end_time - start_time) * 1000)  # 计算时间差ms
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
