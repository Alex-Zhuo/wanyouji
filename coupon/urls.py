# coding: utf-8
from coupon.views import CouponViewSet, UserCouponRecordViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(r'record', CouponViewSet)
router.register(r'user', UserCouponRecordViewSet)
