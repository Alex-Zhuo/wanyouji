# coding: utf-8
from rest_framework.routers import DefaultRouter

from statistical.views import TotalStatisticalViewSet

router = DefaultRouter()

router.register('data', TotalStatisticalViewSet)
