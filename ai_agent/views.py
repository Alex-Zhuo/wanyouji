# coding: utf-8
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils.decorators import method_decorator
from ai_agent.models import DefaultQuestions, HistoryChat, MoodImage, ImageResource
from ai_agent.serializers import DefaultQuestionsSerializer, HistoryChatSerializer, \
    HistoryChatCreateSerializerSerializer, MoodImageSerializer, ImageResourceSerializer
from home.views import ReturnNoDetailViewSet
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.pagination import DefaultNoPagePagination
from restframework_ext.permissions import IsPermittedUser
import logging
from restframework_ext.exceptions import CustomAPIException
from django.views.decorators.cache import cache_page
from caches import get_prefix

log = logging.getLogger(__name__)
PREFIX = get_prefix()


class DefaultQuestionsViewSet(ReturnNoDetailViewSet):
    queryset = DefaultQuestions.objects.filter(is_use=True)
    permission_classes = [IsPermittedUser]
    serializer_class = DefaultQuestionsSerializer
    http_method_names = ['get']

    @method_decorator(cache_page(60, key_prefix=PREFIX))
    def list(self, request, *args, **kwargs):
        return Response(self.serializer_class(self.queryset, many=True, context={'request': request}).data)

    @action(methods=['post', 'get'], detail=False, http_method_names=['post', 'get'])
    def post_question(self, request):
        from qcloud import get_tencent
        client = get_tencent()
        content = request.data.get('question') or request.GET.get('question')
        return client.agent_request_stream('POST', request.user.id, content)

    @action(methods=['post', 'get'], detail=False, http_method_names=['post', 'get'])
    def post_mood(self, request):
        from qcloud import get_tencent
        client = get_tencent()
        content = request.data.get('question') or request.GET.get('question')
        st, data = client.agent_mood_request(request.user.id, content)
        if not st:
            raise CustomAPIException(data)
        return Response(dict(code=data))


class HistoryChatViewSet(ReturnNoDetailViewSet):
    queryset = HistoryChat.objects.all()
    permission_classes = [IsPermittedUser]
    serializer_class = HistoryChatSerializer
    pagination_class = DefaultNoPagePagination
    http_method_names = ['get']
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def post_history(self, request):
        s = HistoryChatCreateSerializerSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()


class MoodImageViewSet(ReturnNoDetailViewSet):
    queryset = MoodImage.objects.all()
    permission_classes = [IsPermittedUser]
    serializer_class = MoodImageSerializer
    http_method_names = ['get']
    filter_fields = ['code']


class ImageResourceViewSet(ReturnNoDetailViewSet):
    queryset = ImageResource.objects.filter(status=ImageResource.STATUS_ON)
    serializer_class = ImageResourceSerializer
    permission_classes = []
    filter_fields = ('code',)
    http_method_names = ['get']
