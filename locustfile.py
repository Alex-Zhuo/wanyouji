from locust import HttpUser, TaskSet, task
import random

class UserBehavior(TaskSet):
    @task
    def index(self):
        token_list =['ca33e656a3801fe0f372772946616e182_1755246705', '8dead708564abab8533c3c7a915b01551_1755245551']
        token = token_list[random.randint(0, 1)]
        print(token)
        self.client.get("/api/users/new_info/?Actoken={}".format(token))


class WebsiteUser(HttpUser):
    tasks = [UserBehavior]

    min_wAIt = 5000

    max_wait = 9000

