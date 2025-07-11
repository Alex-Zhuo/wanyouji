# coding: utf-8

from rest_framework.routers import DefaultRouter

from mp.views import WxAuthViewSet, LpViewSet, BasicConfigViewSet, TikTokViewSet,DouYinImagesViewSet

router = DefaultRouter()

router.register(r'auth', WxAuthViewSet, basename='wxauth')
router.register(r'lprog', LpViewSet, basename='lprog')
router.register(r'basic', BasicConfigViewSet, basename='basic')
# router.register(r'tiktok', TikTokViewSet, basename='tiktokauth')
# router.register(r'dy_images', DouYinImagesViewSet, basename='dy_images')