from locust import HttpUser, TaskSet, task
import random


class UserBehavior(TaskSet):
    @task
    def index(self):
        # token_list =['ca33e656a3801fe0f372772946616e182_1755246705', '8dead708564abab8533c3c7a915b01551_1755245551']
        # token = token_list[random.randint(0, 1)]
        # print(token)
        self.client.get("/api/users/new_info/?Actoken=7acfd418eeb0bfb9f072ec8d29c6bc491_1755329817")


class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    host = "http://127.0.0.1:"
    min_wAIt = 5000

    max_wait = 9000
