# coding: utf-8
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from caches import get_pika_redis, get_redis_name


class Command(BaseCommand):
    help = 'initial streets'

    def handle(self, *args, **options):
        area_path = os.path.join(settings.BASE_DIR, 'streets.json')
        streets_data = dict()
        with open(area_path, 'r', encoding='utf-8') as f:
            streets = json.loads(f.read())
        print(streets)
        for street in streets:
            name = "{}_{}_{}".format(street['provinceCode'], street['cityCode'], street['areaCode'])
            if streets_data.get(name):
                streets_data[name].append(street)
            else:
                streets_data[name] = [street]
        pika = get_pika_redis()
        key = get_redis_name('streets_cache')
        for name, v in streets_data.items():
            pika.hset(key, name, json.dumps(v))
        self.stdout.write(self.style.SUCCESS('\nSuccessfully init streets'))
