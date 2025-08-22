"""ngp URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from rest_framework import routers

from caiyicloud.views import CaiYiViewSet
from dj import technology_admin
# from group_activity.views import ActReceiptViewSet
from kuaishou_wxa.views import KShouWxaViewSet
from mall.views import UserAddressViewSet, HotSearchViewSet, ResourceViewSet, \
    ShareQrcodeBackgroundViewSet, ExpressCompanyViewSet
from mall.views import UserViewSet, ReceiptViewset
# Routers provide an easy way of automatically determining the URL conf.
from restframework_ext.views import page_not_found
from mp.views import JsApiViewSet, MpApi, MpWebView, MpClientView
from shopping_points.urls import router as shopping_points_router
from mall.urls import router as MALL_ROUTER
from mp.urls import router as MPRouter
from ticket.urls import router as SHOW_ROUTER
from express.urls import router as EXPRESS_ROUTER
from common.utils import get_config
from statistical.urls import router as STL_ROUTER
from coupon.urls import router as COUPON_ROUTER
from ticket.views import TicketReceiptViewSet
# from xiaohongshu.views import XhsWxaViewSet
from renovation.urls import router as RENOVATION_ROUTER
from ai_agent.urls import router as AIAGENT_ROUTER

BASE_CONF = get_config()
router = routers.DefaultRouter()
router.register(r'bgimg', ShareQrcodeBackgroundViewSet)
router.register(r'users', UserViewSet)
router.register(r'address', UserAddressViewSet)
router.register(r'hot_search', HotSearchViewSet)
router.register(r'res', ResourceViewSet)
router.register(r'express_com', ExpressCompanyViewSet)
# router.register(r'front_config', MallFrontConfigViewSet, basename='front_config')
router.register(r'jsapi', JsApiViewSet, basename='jsapi')
router.register(r'receipts', ReceiptViewset, basename='receipts')
router.register(r'ticket_receipts', TicketReceiptViewSet, basename='act_receipts')
# router.register(r'act_receipts', ActReceiptViewSet, basename='act_receipts')

router.register(r'mpclient', MpClientView, basename='mpclient')
# router.register(r'tab_pages', SubPagesViewSet)
# router.register(r'mpviewnew', MpViewNew, basename='mpviewnew')
# router.register(r'ks', KShouWxaViewSet, basename='ks')
# router.register(r'xiaohs', XhsWxaViewSet, basename='xhs')
router.register(r'cy', CaiYiViewSet, basename='caiyi')
urlpatterns = [
    url(r'^ueditor/', include('DjangoUeditor.urls')),
    url(r'^{}/'.format(BASE_CONF['admin_url_site_name']), admin.site.urls),
    url(r'^{}/'.format(BASE_CONF['admin_url_site_name_tg']), technology_admin.urls),
    url(r'^api/wmp/', include(MPRouter.urls)),
    url(r'^api/$', page_not_found),
    url(r'^api/', include(router.urls)),
    url(r'^api/mall/', include(MALL_ROUTER.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    # url(r'^api_sz/ajax_select/', include(ajax_select_urls)),
    #  url(r'^_nested_admin/', include('nested_admin.urls')),
    url(r'^api/shopping_points/', include(shopping_points_router.urls)),
    url(r'^api/mp/$', MpApi.as_view()),
    url(r'^api/mpweb/$', MpWebView.as_view(), name='mpweb'),
    # url(r'^api_sz/mp/bank/$', MpPayBankCodeView.as_view()),
    url(r'^api/show/', include(SHOW_ROUTER.urls)),
    url(r'^api/express/', include(EXPRESS_ROUTER.urls)),
    url(r'^api/stl/', include(STL_ROUTER.urls)),
    url(r'^api/coupon/', include(COUPON_ROUTER.urls)),
    url(r'^api/media/', include(RENOVATION_ROUTER.urls)),
    url(r'^api/aiagent/', include(AIAGENT_ROUTER.urls)),
    # url(r'^api_sz/forum/', include(forum_router.urls)),
]
