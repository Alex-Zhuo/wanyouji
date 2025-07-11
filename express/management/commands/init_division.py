# coding: utf-8
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from express.models import Division


class Command(BaseCommand):
    help = 'initial division'

    def handle(self, *args, **options):
        def valid_code(code):
            """
            检查是否为国内地区. 前2为90开始为国外
            :param code:
            :return:
            """
            l = code[:2]
            return int(l) < 90

        area_path = os.path.join(settings.BASE_DIR, 'express/area.json')
        with open(area_path, 'r', encoding='utf-8') as f:
            areas = json.loads(f.read())
            provs = dict()

            for code, province in areas['province_list'].items():
                if valid_code(code):
                    provs[code[:2]] = Division.add_prov(province)
            cities = dict()
            for code, city in areas['city_list'].items():
                if valid_code(code):
                    cities[code[:4]] = Division.add_city(provs[code[:2]].province, city)
            for code, county in areas['county_list'].items():
                if valid_code(code):
                    dcity = cities[code[:4]]
                    Division.add_county(dcity.province, dcity.city, county)

            self.stdout.write(self.style.SUCCESS('\nSuccessfully init division'))
