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
        # ret = json.loads(request.body.decode('utf-8'))
        # message_id = ret['message_id']
        # app_id = ret['app_id']
        # event = ret['event']
        # data = ret['data']
        # ret = {"result": 1, "message_id": message_id}
        # if event == 'POI_AUDITED':
        #     st = KsPoiService.update_status(data['poi_id'], data['app_id'], data['message'], data['reject_reason'])
        #     if not st:
        #         ret['result'] = 0
        # elif event == 'PRODUCT_AUDITED':
        #     st = KsGoodsConfig.set_approve(data['product_id'], data['message'], data['reject_reason'], data['audit_id'])
        #     if not st:
        #         ret['result'] = 0
        return Response(ret)

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def get_seat_url(self, request):
        s = CySeatUrlSerializer(data=request.GET, context=dict(request=request))
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
