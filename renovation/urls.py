from rest_framework import routers

from renovation.views import OpenScreenMediaViewSet

router = routers.DefaultRouter()

router.register('screen', OpenScreenMediaViewSet)