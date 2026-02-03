# coding: utf-8
from rest_framework.routers import DefaultRouter
from blind_box.views import (
    PrizeViewSet, BlindBoxViewSet, WheelActivityViewSet, BlindBoxOrderViewSet, BlindReceiptViewSet,
    LotteryPurchaseRecordViewSet, BlindWinningRecordViewSet,WheelWinningRecordViewSet
)

router = DefaultRouter()

router.register(r'prize', PrizeViewSet, basename='prize')
router.register(r'blind_box', BlindBoxViewSet, basename='blind_box')
router.register(r'blind_order', BlindBoxOrderViewSet, basename='blind_order')
router.register(r'blind_prize', BlindWinningRecordViewSet, basename='blind_prize')
router.register(r'receipt', BlindReceiptViewSet, basename='blind_receipt')
router.register(r'wheel', WheelActivityViewSet, basename='wheel')
router.register(r'wheel_prize', WheelWinningRecordViewSet, basename='wheel_prize')
router.register(r'wheel_order', LotteryPurchaseRecordViewSet, basename='wheel_order')
