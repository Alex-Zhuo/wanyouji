# coding=utf-8
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from blind_box.models import (
    Prize, BlindBox, BlindBoxWinningRecord, WheelWinningRecord, WheelActivity, LotteryPurchaseRecord, BlindBoxOrder,
    BlindReceipt, BlindOrderRefund, SR_GOOD, UserLotteryTimes
)
from blind_box.serializers import (
    PrizeSerializer, BlindBoxSerializer, WheelActivitySerializer,
    BlindBoxWinningRecordSerializer, LotteryPurchaseRecordSerializer, BlindBoxDetailSerializer, PrizeDetailSerializer,
    BlindBoxOrderSerializer, BlindBoxOrderCreateSerializer, BlindBoxOrderPrizeSerializer,
    BlindBoxWinningRecordDetailSerializer, BlindBoxWinningReceiveSerializer, LotteryPurchaseRecordCreateSerializer,
    WheelActivityDrawSerializer
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

log = logging.getLogger(__name__)


class BlindReceiptViewSet(BaseReceiptViewset):
    """
    盲盒和转盘次数支付接口
    """
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
        """
        奖品详情接口
        """
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
        """
        盲盒详情接口
        """
        try:
            obj = BlindBox.objects.get(no=pk)
            data = BlindBoxDetailSerializer(obj, context={'request': request}).data
        except BlindBox.DoesNotExist:
            log.error(pk)
            raise Http404
        return Response(data)


class BlindBoxOrderViewSet(ReturnNoDetailViewSet):
    """
    盲盒订单接口
    """
    queryset = BlindBoxOrder.objects.all()
    serializer_class = BlindBoxOrderSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    filter_fields = ['status']

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def create_order(self, request):
        """
        盲盒下单接口
        """
        with try_queue('blindbox-order', 1, 5) as got:
            if got:
                s = BlindBoxOrderCreateSerializer(data=request.data, context={'request': request})
                s.is_valid(True)
                payno, pay_end_at, order_no = s.create(s.validated_data)
            else:
                log.warning(f"盲盒抢购排队超时失败")
                raise CustomAPIException('当前抢够人数较多，请稍后重试')
        return Response(data=dict(receipt_id=payno, pay_end_at=pay_end_at, order_no=order_no))

    @action(methods=['get'], detail=False)
    def prizes(self, request):
        """
        参数：
        order_no
        查询盲盒订单中奖记录列表
        """
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
        """
        查看实物中奖记录物流
        """
        obj = self.get_object()
        express_no = obj.express_no
        if not obj.can_query_express:
            raise CustomAPIException('还未发货')
        # if order.express_comp_no in ['SFEXPRESS', 'ZTO']:
        #     express_no = '{}:{}'.format(express_no, order.mobile[-4:])
        from qcloud import get_tencent
        client = get_tencent()
        succ, data = client.query_express(obj.id, express_no, obj.express_phone)
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
        """
        盲盒中奖详情
        """
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
        """转盘活动取第一个上架状态的"""
        obj = self.queryset.first()
        data = self.serializer_class(obj, context={'request': request}).data
        return Response(data)

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def draw(self, request):
        """转盘抽奖"""
        s = WheelActivityDrawSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        section = s.create(s.validated_data)
        return Response(data=dict(section_no=section.no))

    @action(methods=['get'], detail=False)
    def rest_times(self, request):
        """获取可用次数"""
        obj = UserLotteryTimes.get_or_create_record(request.user)
        return Response(data=dict(times=obj.times))


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
        """抽奖次数下单"""
        with try_queue('wheel-order', 500, 5) as got:
            if got:
                s = LotteryPurchaseRecordCreateSerializer(data=request.data, context={'request': request})
                s.is_valid(True)
                payno, pay_end_at = s.create(s.validated_data)
            else:
                log.warning(f"转盘次数购买排队超时失败")
                raise CustomAPIException('当前活动火爆，请稍后再试')
        return Response(data=dict(receipt_id=payno, pay_end_at=pay_end_at))
