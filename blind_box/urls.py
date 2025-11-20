# coding: utf-8
from rest_framework.routers import DefaultRouter
from blind_box.views import (
    PrizeViewSet, BlindBoxViewSet, WheelActivityViewSet, BlindBoxOrderViewSet, BlindReceiptViewSet, LotteryPurchaseRecordViewSet
)

router = DefaultRouter()

router.register(r'prize', PrizeViewSet, basename='prize')
router.register(r'blind_box', BlindBoxViewSet, basename='blind_box')
router.register(r'blind_order', BlindBoxOrderViewSet, basename='blind_order')
router.register(r'receipt', BlindReceiptViewSet, basename='blind_receipt')
router.register(r'wheel', WheelActivityViewSet, basename='wheel')
router.register(r'wheel_order', LotteryPurchaseRecordViewSet, basename='wheel_order')
