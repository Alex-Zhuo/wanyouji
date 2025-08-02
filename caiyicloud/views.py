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
from caiyicloud.models import CyOrder
from caiyicloud.api import caiyi_cloud
from caiyicloud.serializers import CySeatUrlSerializer
log = logger = logging.getLogger(__name__)


class CaiYiViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['post', 'get'], detail=False, permission_classes=[])
    def cy_notify(self, request):
        log.error(request.data)
        # log.error(request.body)
        log.error(request.META)
        ret = dict(code=200, resp_code="000000", msg="成功", trace_id=uuid.uuid4().hex)
        return JsonResponse(ret)
        # data = request.data
        # cy = caiyi_cloud()
        # header = data['header']
        # event_type = header['event_type']
        # sign = header['sign']
        # cy = 1
        # sign_dict = dict(version=data['version'], event_id=header['event_id'], event_type=event_type,
        #                  create_time=header['create_time'], app_id=header['event_id'])
        # sign_content = do_check(sign_dict,sign)
        #
        # if event_type == 'ticket.stock.sync':
        #     # 库存变更通知
        #     pass

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def get_seat_url(self, request):
        s = CySeatUrlSerializer(data=request.data, context=dict(request=request))
        s.is_valid(True)
        ret = s.create(s.validated_data)
        return Response(ret)

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedUser])
    def get_seat_info(self, request):
        biz_id = request.GET.get('biz_id')
        if not biz_id:
            raise CustomAPIException('获取已选择信息失败')
        ret = CyOrder.get_cy_seat_info(biz_id=request.GET.get('biz_id'))
        return Response(ret)
