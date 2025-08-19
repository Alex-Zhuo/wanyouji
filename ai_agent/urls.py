# coding: utf-8
from rest_framework.routers import DefaultRouter

from ai_agent.views import DefaultQuestionsViewSet, HistoryChatViewSet, MoodImageViewSet,ImageResourceViewSet

router = DefaultRouter()

router.register('questions', DefaultQuestionsViewSet)
router.register('history', HistoryChatViewSet)
router.register('mood', MoodImageViewSet)
router.register('resource', ImageResourceViewSet)
