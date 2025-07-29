# coding: utf-8
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import viewsets

from ai_agent.models import DefaultQuestions, HistoryChatDetail
from ai_agent.serializers import DefaultQuestionsSerializer, HistoryChatDetailSerializer
from home.views import ReturnNoDetailViewSet
from restframework_ext.pagination import DefaultNoPagePagination
from restframework_ext.permissions import IsPermittedUser
import logging

log = logging.getLogger(__name__)


class DefaultQuestionsViewSet(ReturnNoDetailViewSet):
    queryset = DefaultQuestions.objects.filter(is_use=True)
    permission_classes = [IsPermittedUser]
    serializer_class = DefaultQuestionsSerializer
    http_method_names = ['get']


class HistoryChatDetailViewSet(ReturnNoDetailViewSet):
    queryset = HistoryChatDetail.objects.all()
    permission_classes = [IsPermittedUser]
    serializer_class = HistoryChatDetailSerializer
    pagination_class = DefaultNoPagePagination
    http_method_names = ['get']

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def set_answer(self, request):
        s = UserCouponRecordCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def set_question(self, request):
        s = UserCouponRecordCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()