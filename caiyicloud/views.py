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
        ret_error = dict(code=500, resp_code="100000", msg="失败", trace_id=uuid.uuid4().hex)
        return JsonResponse(ret)

        data = request.data
        cy = caiyi_cloud()
        header = data['header']
        event = data['event']
        event_type = header['event_type']
        sign = header['sign']
        sign_dict = dict(version=data['version'], event_id=header['event_id'], event_type=event_type,
                         create_time=header['create_time'], app_id=header['app_id'])
        if event_type == 'order.issue.ticket':
            sign_dict.update(dict(cyy_order_no=event['cyy_order_no'], supplier_id=event['supplier_id']))
        is_sign = cy.do_check_sign(sign_dict, sign)
        is_success = True
        if not is_sign:
            ret_error['msg'] = '验签失败'
            is_success = False
        else:
            if event_type == 'order.issue.ticket':
                # 订单出票通知
                cyy_order_no = event['cyy_order_no']
                st, msg = CyOrder.notify_issue_ticket(cyy_order_no)
                if not st:
                    ret_error['msg'] = msg
        if is_success:
            return JsonResponse(ret)
        else:
            return JsonResponse(ret_error)

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
