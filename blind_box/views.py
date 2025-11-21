# coding=utf-8
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from blind_box.models import (
    Prize, BlindBox, BlindBoxWinningRecord, WheelWinningRecord, WheelActivity, LotteryPurchaseRecord, BlindBoxOrder,
    BlindReceipt, BlindOrderRefund, SR_GOOD, WinningRecordAbstract
)
from blind_box.serializers import (
    PrizeSerializer, BlindBoxSerializer, WheelActivitySerializer,
    BlindBoxWinningRecordSerializer, LotteryPurchaseRecordSerializer, BlindBoxDetailSerializer, PrizeDetailSerializer,
    BlindBoxOrderSerializer, BlindBoxOrderCreateSerializer, BlindBoxOrderPrizeSerializer,
    BlindBoxWinningRecordDetailSerializer, BlindBoxWinningReceiveSerializer
)
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.pagination import StandardResultsSetPagination
from home.views import ReturnNoDetailViewSet, DetailPKtoNoViewSet
import logging
from django.http import Http404

from restframework_ext.views import BaseReceiptViewset
from django.shortcuts import get_object_or_404
from concu.api_limit import try_queue
from caches import run_with_lock, get_redis_name

log = logging.getLogger(__name__)


class BlindReceiptViewSet(BaseReceiptViewset):
    permission_classes = []
    receipt_class = BlindReceipt
    refund_class = BlindOrderRefund

    def before_pay(self, request, pk):
        receipt = get_object_or_404(self.receipt_class, payno=pk)
        now = timezone.now()
        order = None
        unpaid_status = None
        if receipt.biz == receipt.BIZ_BLIND:
            order = receipt.blind_receipt
            unpaid_status = order.ST_DEFAULT
        elif receipt.biz == receipt.BIZ_LOTTERY:
            order = receipt.lottery_receipt
            unpaid_status = order.ST_UNPAID
        if not order:
            raise CustomAPIException('找不到订单')
        if order and order.status != unpaid_status:
            raise CustomAPIException('订单状态错误')
        # receipt.query_status(order.order_no)
        # if receipt.paid:
        #     raise CustomAPIException('该订单已经付款，请尝试刷新订单页面')
        if order.pay_end_at <= now:
            order.cancel()
            raise CustomAPIException('该订单支付过期，请重新下单')


class PrizeViewSet(DetailPKtoNoViewSet, ReturnNoDetailViewSet):
    """奖品列表"""
    queryset = Prize.objects.filter(status=Prize.STATUS_ON, stock__gt=0)
    permission_classes = [IsPermittedUser]
    serializer_class = PrizeSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['get'], detail=True)
    def details(self, request, pk):
        try:
            obj = Prize.objects.get(no=pk)
            data = PrizeDetailSerializer(obj, context={'request': request}).data
        except Prize.DoesNotExist:
            log.error(pk)
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
        with try_queue('blindbox-order', 1, 5) as got:
            if got:
                s = BlindBoxOrderCreateSerializer(data=request.data, context={'request': request})
                s.is_valid(True)
                order = s.create(s.validated_data)
            else:
                log.warning(f"盲盒抢购排队超时失败")
                raise CustomAPIException('当前抢够人数较多，请稍后重试')
        return Response(data=dict(receipt_id=order.receipt.payno, pay_end_at=order.pay_end_at, order_no=order.order_no))

    @action(methods=['get'], detail=False)
    def prizes(self, request):
        order_no = request.GET.get('order_no')
        try:
            order = self.queryset.get(order_no=order_no, user=request.user, status=BlindBoxOrder.ST_PAID)
            qs = order.blind_box_items.exclude(status=BlindBoxWinningRecord.ST_UNPAID)
            data = BlindBoxOrderPrizeSerializer(qs, many=True, context={'request': request}).data
            return Response(data)
        except BlindBox.DoesNotExist:
            raise CustomAPIException('订单未支付')


class WinningRecordCommonViewSet(DetailPKtoNoViewSet, ReturnNoDetailViewSet):
    @action(methods=['get'], detail=True)
    def query_express(self, request, pk):
        # 查看物流
        order = self.get_object()
        express_no = order.express_no
        # if order.express_comp_no in ['SFEXPRESS', 'ZTO']:
        #     express_no = '{}:{}'.format(express_no, order.mobile[-4:])
        from qcloud import get_tencent
        client = get_tencent()
        succ, data = client.query_express(order.id, express_no, order.express_phone)
        if succ:
            return Response(data)
        else:
            raise CustomAPIException(data)


class BlindWinningRecordViewSet(WinningRecordCommonViewSet):
    """盲盒中奖记录"""
    queryset = BlindBoxWinningRecord.objects.exclude(status=BlindBoxWinningRecord.ST_UNPAID)
    permission_classes = [IsPermittedUser]
    serializer_class = BlindBoxWinningRecordSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    http_method_names = ['get']

    @action(methods=['get'], detail=True)
    def details(self, request, pk):
        try:
            obj = self.get_object()
            data = BlindBoxWinningRecordDetailSerializer(obj, context={'request': request}).data
        except BlindBoxWinningRecord.DoesNotExist:
            log.error(pk)
            raise Http404
        return Response(data)

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def receive(self, request):
        """实物领取奖品"""
        s = BlindBoxWinningReceiveSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()

    @action(methods=['post'], detail=True, http_method_names=['post'])
    def confirm(self, request, pk):
        """确认收货（实物奖品）"""
        obj = self.get_object()
        if obj.source_type != SR_GOOD:
            raise CustomAPIException('该奖品类型不支持此操作')
        if obj.status != BlindBoxWinningRecord.ST_PENDING_RECEIPT:
            raise CustomAPIException('待收货状态才能确认')
        obj.set_completed()
        return Response()


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


#
class LotteryPurchaseRecordViewSet(ReturnNoDetailViewSet):
    """抽奖次数购买记录"""
    queryset = LotteryPurchaseRecord.objects.all()
    permission_classes = [IsPermittedUser]
    serializer_class = LotteryPurchaseRecordSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    filter_fields = ['status']
    http_method_names = ['get']

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def create_order(self, request):
        with try_queue('wheel-order', 100, 5) as got:
            if got:
                s = BlindBoxOrderCreateSerializer(data=request.data, context={'request': request})
                s.is_valid(True)
                order = s.create(s.validated_data)
            else:
                log.warning(f"盲盒抢购排队超时失败")
                raise CustomAPIException('当前抢够人数较多，请稍后重试')
        return Response(data=dict(receipt_id=order.receipt.payno, pay_end_at=order.pay_end_at))
