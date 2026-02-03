# coding: utf-8
from activity.views import ActivitiesViewSet, UserApplyRecordViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register('acts', ActivitiesViewSet)
router.register('apply', UserApplyRecordViewSet)
