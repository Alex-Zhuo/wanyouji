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
from caiyicloud.models import CyOrder, CaiYiCloudApp
from caiyicloud.api import caiyi_cloud
from caiyicloud.serializers import CySeatUrlSerializer, GetPromoteActivitySerializer
from datetime import datetime

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
        ret = CyOrder.get_cy_seat_info(biz_id=request.GET.get('biz_id'))
        return Response(ret)

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def check_promote(self, request):
        s = GetPromoteActivitySerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        ret_promote_amount, act_data = s.create(s.validated_data)
        return Response(dict(ret_promote_amount=ret_promote_amount, act_data=act_data))
