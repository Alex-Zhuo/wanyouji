# coding: utf-8

from rest_framework.routers import DefaultRouter

from mp.views import WxAuthViewSet, LpViewSet, BasicConfigViewSet

router = DefaultRouter()

router.register(r'auth', WxAuthViewSet, basename='wxauth')
router.register(r'lprog', LpViewSet, basename='lprog')
router.register(r'basic', BasicConfigViewSet, basename='basic')