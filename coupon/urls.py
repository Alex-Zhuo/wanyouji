# coding: utf-8
from coupon.views import CouponViewSet, UserCouponRecordViewSet, CouponReceiptViewSet, CouponOrderViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(r'record', CouponViewSet)
router.register(r'user', UserCouponRecordViewSet)
router.register(r'receipt', CouponReceiptViewSet, basename='coupon_receipt')
router.register(r'order', CouponOrderViewSet, basename='coupon_order')