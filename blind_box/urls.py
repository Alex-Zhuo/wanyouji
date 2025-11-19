# coding: utf-8
from rest_framework.routers import DefaultRouter
from blind_box.views import (
    PrizeViewSet, BlindBoxViewSet, WheelActivityViewSet,
    WinningRecordViewSet, LotteryPurchaseRecordViewSet
)

router = DefaultRouter()

router.register(r'prize', PrizeViewSet, basename='prize')
router.register(r'blind-box', BlindBoxViewSet, basename='blind-box')
router.register(r'wheel-activity', WheelActivityViewSet, basename='wheel-activity')
router.register(r'winning-record', WinningRecordViewSet, basename='winning-record')
router.register(r'lottery-purchase', LotteryPurchaseRecordViewSet, basename='lottery-purchase')

