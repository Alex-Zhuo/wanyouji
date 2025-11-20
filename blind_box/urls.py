# coding: utf-8
from rest_framework.routers import DefaultRouter
from blind_box.views import (
    PrizeViewSet, BlindBoxViewSet, WheelActivityViewSet
)

router = DefaultRouter()

router.register(r'prize', PrizeViewSet, basename='prize')
router.register(r'blind_box', BlindBoxViewSet, basename='blind_box')
router.register(r'wheel', WheelActivityViewSet, basename='wheel')

