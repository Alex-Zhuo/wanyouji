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
        return ret.text, status


async def main():
    async with aiohttp.ClientSession() as session:
        async with get_pika_redis() as redis:
            for i in list(range(0, 100)):
                token = await redis.lindex('test_token', i)
                st = False
                start_time = time.time()
                data, status = await fetch(session, f"http://127.0.0.1:8168/api/users/new_info/?Actoken={token}")
                if 200 <= status < 300:
                    st = True
                end_time = time.time()
                elapsed_ms = int((end_time - start_time) * 1000)  # 计算时间差ms
                print('{},{}'.format(elapsed_ms, st))


asyncio.run(main())
