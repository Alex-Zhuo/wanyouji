# coding: utf-8
from rest_framework.routers import DefaultRouter

from ai_agent.views import DefaultQuestionsViewSet

router = DefaultRouter()

router.register('questions', DefaultQuestionsViewSet)