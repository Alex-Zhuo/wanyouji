"""

# this module is the entrypoint.
## how to run
## uvicorn main:app --reload --port 9001 --host 0.0.0.0
## test it:  http://localhost:9001/

"""
from fastapi import FastAPI
import orjson
from fastapi.responses import ORJSONResponse
import logging
from django.core.asgi import get_asgi_application
from redis import StrictRedis
from fastapi import Request as FastAPIRequest
from concurrent.futures import ThreadPoolExecutor
import asyncio
import os
from typing import Dict
import yaml

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dj.settings')
django_app = get_asgi_application()

BASE_DIR = os.path.dirname(__file__)
executor = ThreadPoolExecutor(max_workers=20)

app = FastAPI(default_response_class=ORJSONResponse)
log = logging.getLogger(__name__)

_config = None
_pika_redis = None


def get_config() -> Dict:
    global _config
    if not _config:
        _config = yaml.safe_load(open(os.path.join(BASE_DIR, 'env.yml'), encoding='utf-8'))
    return _config


def get_prefix():
    redis_conf = get_config().get('redis')
    return redis_conf['prefix']


def get_redis_name(name):
    prefix = get_prefix()
    return prefix + '_' + name


def pika_redis():
    global _pika_redis
    if not _pika_redis:
        conf = get_config()
        host = '127.0.0.1'
        db = 0
        port = 6379
        if conf and conf.get('pika'):
            port = conf.get('pika').get('port', 9221)
            host = conf.get('pika').get('host', '127.0.0.1')
            db = conf.get('pika').get('db', 0)
        _pika_redis = StrictRedis(host=host, port=port, db=db, decode_responses=True)
    return _pika_redis


#
# @app.get("/tapi/szpw/info/")
# async def info(req: FastAPIRequest):
#     # log.error(req)
#     config = get_config()
#     # log.error(config)
#     token = req.headers.get('actoken') or req.query_params.get('token')
#     # log.error(token)
#     # from mall.user_cache import token_to_cache_user
#     # user = token_to_cache_user(token)
#     # log.error(user.id)
#     share_code = req.query_params.get('share_code')
#     if not token:
#         return ORJSONResponse(status_code=403, content=dict(msg='token不能为空'))
#     else:
#         pika = pika_redis()
#         t_key = get_redis_name('token_info_{}'.format(token))
#         s_key = get_redis_name('share_task')
#         # with get_pika_redis_c() as pika:
#         user_info = pika.get(t_key)
#         if not user_info:
#             return ORJSONResponse(status_code=403, content=dict(msg='请重新登录'))
#         user_info = orjson.loads(user_info)
#         user_info['token'] = token
#         if user_info.get('avatar') and 'http' not in user_info['avatar']:
#             user_info['avatar'] = f"{config['template_url']}/{user_info['avatar']}"
#         if share_code and user_info.get('share_code'):
#             # 处理任务
#             pika.hset(s_key, user_info['share_code'], share_code)
#             pika.expire(s_key, 60)
#         return user_info


@app.get("/tapi/szpw/new_info/")
async def new_info(req: FastAPIRequest):
    config = get_config()
    token = req.headers.get('actoken') or req.query_params.get('token')
    from mall.user_cache import token_to_cache_user
    user = token_to_cache_user(token)
    if not user:
        return ORJSONResponse(status_code=403, content=dict(msg='请重新登录'))
    share_code = req.query_params.get('share_code')
    if share_code:
        from restframework_ext.exceptions import CustomAPIException
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(executor, lambda: user.bind_parent(share_code))
        except CustomAPIException as e:
            log.error(e)
            return ORJSONResponse(status_code=e.status_code, content=dict(msg=e.msg))
        except Exception as e:
            log.error('绑定上级失败')
    from mall.serializers import UserInfoCacheSerializer
    user_info = UserInfoCacheSerializer(user).data
    if user_info.get('avatar') and 'http' not in user_info['avatar']:
        user_info['avatar'] = f"{config['template_url']}/{user_info['avatar']}"
    return user_info


class DjRequest:
    def __init__(self, data, user, header, query_params):
        self.data = data
        self.user = user
        self.META = header
        self.query_params = query_params


@app.post("/tapi/szpw/noseat_order/")
async def noseat_order(req: FastAPIRequest):
    token = req.headers.get('actoken') or req.query_params.get('token')
    if not token:
        return ORJSONResponse(status_code=403, content=dict(msg='token不能为空'))
    body = await req.body()
    if body:
        data = orjson.loads(body)
    else:
        return ORJSONResponse(status_code=403, content=dict(msg='参数错误'))
    from mall.user_cache import token_to_cache_user
    user = token_to_cache_user(token)
    if not user:
        return ORJSONResponse(status_code=403, content=dict(msg='请重新登陆'))
    django_request = DjRequest(data, user, req.headers, req.query_params)
    loop = asyncio.get_event_loop()
    from restframework_ext.exceptions import CustomAPIException
    from ticket.order_serializer_new import TicketOrderOnSeatNewCreateSerializer

    def noseat_order_debug(dj_request):
        data = dj_request.data
        user = dj_request.user
        data['user'] = user
        if user.forbid_order:
            raise CustomAPIException('用户异常，请联系客服')
        s = TicketOrderOnSeatNewCreateSerializer(data=django_request.data, context={'request': dj_request})
        s._validated_data = dict()
        s._errors = {}
        s.is_valid(True)
        order, payno, prepare_order, pay_end_at, ks_order_info, xhs_order_info = s.create(data)
        data = dict(receipt_id=payno, prepare_order=prepare_order, pay_end_at=pay_end_at,
                    order_id=order.order_no, ks_order_info=ks_order_info, xhs_order_info=xhs_order_info)
        # log.warning(f"got the queue and exec over")
        return data

    try:
        data = await loop.run_in_executor(executor, lambda: noseat_order_debug(django_request))
        return data
    except CustomAPIException as e:
        log.error(e)
        return ORJSONResponse(status_code=e.status_code, content=dict(msg=e.msg))
    except Exception as e:
        log.error(e)
        return ORJSONResponse(status_code=400, content=dict(msg='下单失败'))

# @app.get("/tapi/szpw/test_order/")
# async def test_order(req: FastAPIRequest):
#     # token = req.headers.get('actoken') or req.query_params.get('token')
#     # if not token:
#     #     return ORJSONResponse(status_code=403, content=dict(msg='token不能为空'))
#     # # body = await req.body()
#     # # data = orjson.loads(body)
#     # from mall.user_cache import token_to_cache_user
#     # user = token_to_cache_user(token)
#     # if not user:
#     #     return ORJSONResponse(status_code=403, content=dict(msg='请重新登陆'))
#     from mp.models import BasicConfig
#     from ticket.models import TicketOrder
#     def create_order():
#         inst = TicketOrder.objects.create(user_id=1, u_user_id=1, u_agent_id=2, title='ddd', session_id=1, venue_id=1,
#                                           mobile='123', multiply=1, amount=10)
#         bc = BasicConfig.get()
#         return inst.id
#
#     loop = asyncio.get_event_loop()
#     resp = await loop.run_in_executor(executor, create_order)
#     return dict(code=resp)
