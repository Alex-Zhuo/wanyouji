# coding=utf-8
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from blind_box.models import (
    Prize, BlindBox, BlindBoxWinningRecord, WheelWinningRecord, WheelActivity, LotteryPurchaseRecord, BlindBoxOrder
)
from blind_box.serializers import (
    PrizeSerializer, BlindBoxSerializer, WheelActivitySerializer,
    WinningRecordSerializer, LotteryPurchaseRecordSerializer, BlindBoxDetailSerializer, PrizeDetailSerializer,
    BlindBoxOrderSerializer, BlindBoxOrderCreateSerializer
)
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.pagination import StandardResultsSetPagination
from home.views import ReturnNoDetailViewSet, DetailPKtoNoViewSet
from blind_box.stock_updater import prsc
import logging
import simplejson as json
from django.http import Http404

log = logging.getLogger(__name__)


class PrizeViewSet(DetailPKtoNoViewSet, ReturnNoDetailViewSet):
    """奖品列表"""
    queryset = Prize.objects.filter(status=Prize.STATUS_ON, stock__gt=0)
    permission_classes = [IsPermittedUser]
    serializer_class = PrizeSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['get'], detail=True)
    def details(self, request, no):
        try:
            obj = Prize.objects.get(no=no)
            data = PrizeDetailSerializer(obj, context={'request': request}).data
        except Prize.DoesNotExist:
            log.error(no)
            raise Http404
        return Response(data)


class BlindBoxViewSet(DetailPKtoNoViewSet, ReturnNoDetailViewSet):
    """盲盒列表"""
    queryset = BlindBox.objects.filter(status=BlindBox.STATUS_ON, stock__gt=0)
    permission_classes = [IsPermittedUser]
    serializer_class = BlindBoxSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['get'], detail=True)
    def details(self, request, pk):
        try:
            obj = BlindBox.objects.get(no=pk)
            data = BlindBoxDetailSerializer(obj, context={'request': request}).data
        except BlindBox.DoesNotExist:
            log.error(pk)
            raise Http404
        return Response(data)


class BlindBoxOrderViewSet(ReturnNoDetailViewSet):
    queryset = BlindBoxOrder.objects.all()
    serializer_class = BlindBoxOrderSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    filter_fields = ['status']

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def create_order(self, request):
        from concu.api_limit import try_queue
        with try_queue('blindbox-order', 1, 3) as got:
            if got:
                s = BlindBoxOrderCreateSerializer(data=request.data, context={'request': request})
                s.is_valid(True)
                order = s.create(s.validated_data)
            else:
                log.warning(f"盲盒抢购排队超时失败")
                raise CustomAPIException('当前抢够人数较多，请稍后重试')
        return Response(data=dict(receipt_id=order.receipt.payno, pay_end_at=order.pay_end_at))


class WheelActivityViewSet(ReturnNoDetailViewSet):
    """转盘活动列表"""
    queryset = WheelActivity.objects.filter(status=WheelActivity.STATUS_ON)
    permission_classes = [IsPermittedUser]
    serializer_class = WheelActivitySerializer
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        obj = self.queryset.first()
        data = self.serializer_class(obj, context={'request': request}).data
        return Response(data)
    #
    # @action(methods=['post'], detail=True)
    # def draw(self, request, pk=None):
    #     """转盘抽奖"""
    #     wheel_activity = self.get_object()
    #     user = request.user
    #     with transaction.atomic():
    #         winning_record = draw_wheel_prize(wheel_activity, user)
    #         if not winning_record:
    #             raise CustomAPIException('抽奖失败，请稍后重试')
    #     return Response(WinningRecordSerializer(winning_record, context={'request': request}).data)

# class BlindWinningRecordViewSet(ReturnNoDetailViewSet):
#     """中奖记录"""
#     queryset = BlindBoxWinningRecord.objects.all()
#     permission_classes = [IsPermittedUser]
#     serializer_class = WinningRecordSerializer
#     pagination_class = StandardResultsSetPagination
#     filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
#     filter_fields = ['status', 'source_type']
#     http_method_names = ['get', 'post', 'patch']
#
#     @action(methods=['post'], detail=True)
#     def receive(self, request, pk=None):
#         """领取奖品（纸质票、券码类型）"""
#         winning_record = self.get_object()
#
#         if winning_record.source_type not in [Prize.SR_TICKET, Prize.SR_CODE]:
#             raise CustomAPIException('该奖品类型不支持此操作')
#
#         if winning_record.status != WinningRecord.ST_PENDING_RECEIVE:
#             raise CustomAPIException('该中奖记录状态不正确')
#
#         # 弹窗提示用户联系客服
#         return Response({
#             'message': '请联系在线客服提供中奖记录信息领取奖品！',
#             'winning_no': winning_record.no
#         })
#
#     @action(methods=['post'], detail=True)
#     def confirm_receipt(self, request, pk=None):
#         """确认收货（实物奖品）"""
#         winning_record = self.get_object()
#
#         if winning_record.source_type != Prize.SR_GOOD:
#             raise CustomAPIException('该奖品类型不支持此操作')
#
#         if winning_record.status != WinningRecord.ST_PENDING_RECEIPT:
#             raise CustomAPIException('该中奖记录状态不正确')
#
#         winning_record.set_completed()
#         return Response({'message': '确认收货成功'})
#
#
# class LotteryPurchaseRecordViewSet(ReturnNoDetailViewSet):
#     """抽奖次数购买记录"""
#     queryset = LotteryPurchaseRecord.objects.all()
#     permission_classes = [IsPermittedUser]
#     serializer_class = LotteryPurchaseRecordSerializer
#     pagination_class = StandardResultsSetPagination
#     filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
#     filter_fields = ['status', 'wheel_activity']
#     http_method_names = ['get']
