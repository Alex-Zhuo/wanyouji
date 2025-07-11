from rest_framework import routers

from renovation.views import OpenScreenMediaSet

router = routers.DefaultRouter()

router.register('screen', OpenScreenMediaSet)