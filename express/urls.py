# coding: utf-8
from rest_framework.routers import DefaultRouter

from express.views import CityViewSet

router = DefaultRouter()

router.register('city', CityViewSet)
