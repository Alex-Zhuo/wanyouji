# coding: utf-8
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import viewsets

from ai_agent.models import DefaultQuestions
from ai_agent.serializers import DefaultQuestionsSerializer
from restframework_ext.permissions import IsPermittedUser
import logging

log = logging.getLogger(__name__)


class DefaultQuestionsViewSet(viewsets.ModelViewSet):
    queryset = DefaultQuestions.objects.filter(is_use=True)
    permission_classes = [IsPermittedUser]
    serializer_class = DefaultQuestionsSerializer
    http_method_names = ['get']
