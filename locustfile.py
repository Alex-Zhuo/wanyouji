from locust import HttpUser, TaskSet, task
import random


def get_pika_redis():
    from redis import StrictRedis
    return StrictRedis(host='172.16.0.10:9221', port=9221, db=1, decode_responses=True)


class UserBehavior(TaskSet):
    @task
    def index(self):
        # token_list =['ca33e656a3801fe0f372772946616e182_1755246705', '8dead708564abab8533c3c7a915b01551_1755245551']
        # token = token_list[random.randint(0, 1)]
        # print(token)
        {"pay_type": 7, "multiply": 1, "amount": 22, "actual_amount": 19.8, "mobile": "15577150426",
         "session_id": "e5a1942ff1d44fc3be86d3748a96c8d6", "ticket_list": [{"level_id": 192, "multiply": 1}],
         "channel_type": 1}
        self.client.post("/api/users/new_info/?Actoken=7acfd418eeb0bfb9f072ec8d29c6bc491_1755329817")


class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    host = "http://127.0.0.1:"
    min_wAIt = 5000

    max_wait = 9000
