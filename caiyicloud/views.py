# -*- coding: utf-8 -*-
from rest_framework import viewsets, status
from rest_framework.decorators import action
import logging
from rest_framework.response import Response
from django.http.response import HttpResponse, JsonResponse, HttpResponseRedirect
import json
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser
import jwt
import uuid
from caiyicloud.models import CyOrder, CaiYiCloudApp, PromoteActivity
from caiyicloud.api import caiyi_cloud
from caiyicloud.serializers import CySeatUrlSerializer, CheckPromoteActivitySerializer, \
    PromoteActivitySerializer, PromoteActivityDetailSerializer
from datetime import datetime
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from caches import get_prefix

PREFIX = get_prefix()
log = logger = logging.getLogger(__name__)


class CaiYiViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['post', 'get'], detail=False, permission_classes=[])
    def cy_notify(self, request):
        # 彩艺回调处理
        log.debug(request.data)
        # log.error(request.body)
        # log.debug(request.META)
        ret = dict(code=200, resp_code="000000", msg="成功", trace_id=uuid.uuid4().hex)
        ret_error = dict(code=500, resp_code="100000", msg="失败", trace_id=uuid.uuid4().hex)
        # return JsonResponse(ret)
        data = request.data
        is_success, error_msg = CaiYiCloudApp.due_notify(data)
        if is_success:
            log.debug(ret)
            return JsonResponse(ret)
        else:
            if error_msg:
                ret_error['msg'] = error_msg
            log.debug(ret_error)
            return JsonResponse(ret_error)

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def get_seat_url(self, request):
        # 获取座位h5
        s = CySeatUrlSerializer(data=request.data, context=dict(request=request))
        s.is_valid(True)
        ret = s.create(s.validated_data)
        return Response(ret)

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedUser])
    def get_seat_info(self, request):
        # 获取h5选座座位信息
        biz_id = request.GET.get('biz_id')
        if not biz_id:
            raise CustomAPIException('获取已选择信息失败')
        ret = CyOrder.get_cy_seat_info(user_id=request.user.id, biz_id=request.GET.get('biz_id'))
        return Response(ret)

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def check_promote(self, request):
        s = CheckPromoteActivitySerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        has_promote, act_data, order_promote_data = s.create(s.validated_data)
        return Response(dict(has_promote=has_promote, act_data=act_data, order_promote_data=order_promote_data))

    # @method_decorator(cache_page(60, key_prefix=PREFIX))
    @action(methods=['get'], detail=False, permission_classes=[IsPermittedUser])
    def get_promotes(self, request):
        show_no = request.GET.get('show_no')
        log.debug(show_no)
        if not show_no:
            raise CustomAPIException('参数错误')
        event_qs, ticket_qs = PromoteActivity.get_promotes_show(show_no)
        show_promotes = None
        ticket_promotes = None
        if event_qs:
            show_promotes = PromoteActivitySerializer(event_qs, many=True, context={'request': request}).data
        if ticket_qs:
            ticket_promotes = PromoteActivityDetailSerializer(ticket_qs, many=True, context={'request': request}).data
        return Response(dict(show_promotes=show_promotes, ticket_promotes=ticket_promotes))
