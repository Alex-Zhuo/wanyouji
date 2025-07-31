# -*- coding: utf-8 -*-
from rest_framework import viewsets, status
from rest_framework.decorators import action
import logging
from rest_framework.response import Response
from django.http.response import HttpResponse, JsonResponse, HttpResponseRedirect
import json
from kuaishou_wxa.models import KsUser, KsPoiService, KsGoodsConfig
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser
import jwt

log = logger = logging.getLogger(__name__)


class CaiYiViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(methods=['post', 'get'], detail=False, permission_classes=[])
    def cy_notify(self, request):
        log.error(request.data)
        # log.error(request.body)
        log.error(request.META)
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
        return Response()

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedUser])
    def get_seat_url(self, request):
        from caiyicloud.serializers import CySeatUrlSerializer
        s = CySeatUrlSerializer(data=request.GET, context=dict(request=request))
        s.is_valid(True)
        ret = s.create(s.validated_data)
        return Response(ret)

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedUser])
    def get_seat_info(self, request):
        from caiyicloud.models import CyTicketType
        biz_id = request.GET.get('biz_id')
        if not biz_id:
            raise CustomAPIException('获取已选择信息失败')
        ret = CyTicketType.get_seat_info(biz_id=request.GET.get('biz_id'))
        return Response(ret)
