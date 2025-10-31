# coding:utf-8
from rest_framework.response import Response
from coupon.models import Coupon, UserCouponRecord, CouponBasic, CouponActivity, CouponReceipt, CouponOrderRefund,  CouponOrder
from coupon.serializers import CouponSerializer, UserCouponRecordSerializer, UserCouponRecordCreateSerializer, \
    UserCouponRecordAvailableNewSerializer, CouponActivitySerializer, UserCouponRecordActCreateSerializer, \
    CouponOrderSerializer, CouponOrderDetailSerializer, CouponOrderCreateSerializer
from home.views import ReturnNoDetailViewSet, ReturnNoneViewSet
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.pagination import StandardResultsSetPagination
from restframework_ext.permissions import IsPermittedUser
from rest_framework.decorators import action
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.views import BaseReceiptViewset
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import logging
from django.http import Http404

log = logging.getLogger(__name__)


class CouponViewSet(ReturnNoDetailViewSet):
    """
    消费卷列表
    """
    queryset = Coupon.objects.filter(status=Coupon.STATUS_ON)
    permission_classes = [IsPermittedUser]
    serializer_class = CouponSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def receive(self, request):
        """
        领取消费卷
        """
        s = UserCouponRecordCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()

    @action(methods=['get'], detail=False)
    def activity(self, request):
        """
        消费卷活动详情
        """
        act_no = request.GET.get('act_no')
        if not act_no:
            raise CustomAPIException('活动不存在')
        try:
            c_act = CouponActivity.objects.get(no=act_no, status=CouponActivity.ST_ON)
        except CouponActivity.DoesNotExist:
            raise CustomAPIException('活动已结束')
        data = CouponActivitySerializer(c_act, context={'request': request}).data
        return Response(data)

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def act_receive(self, request):
        """
        活动领取批量消费卷,一键领取
        """
        # log.error(request.data)
        s = UserCouponRecordActCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()


class UserCouponRecordViewSet(ReturnNoDetailViewSet):
    """
    用戶消費卷记录
    """
    queryset = UserCouponRecord.objects.all()
    serializer_class = UserCouponRecordSerializer
    permission_classes = [IsPermittedUser]
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    http_method_names = ['get', 'post']
    filter_fields = ['status']

    @action(methods=['post'], detail=False)
    def get_available_new(self, request):
        """
        查看可使用消費卷
        """
        s = UserCouponRecordAvailableNewSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        res = s.create(s.validated_data)
        return Response(self.serializer_class(res, many=True, context={'request': request}).data)

    @action(methods=['get'], detail=False)
    def pop_up(self, request):
        """
        用户是否弹窗
        """
        has_coupon = Coupon.objects.filter(status=Coupon.STATUS_ON).exists()
        data = dict(need_pop=False, img=None)
        if has_coupon:
            has = Coupon.get_pop_up(request.user.id)
            need_pop = False if has else True
            if not has:
                bc = CouponBasic.get()
                if bc:
                    data['img'] = request.build_absolute_uri(bc.image.url)
                else:
                    need_pop = False
            data['need_pop'] = need_pop
        return Response(data)


class CouponReceiptViewSet(BaseReceiptViewset):
    permission_classes = []
    receipt_class = CouponReceipt
    refund_class = CouponOrderRefund

    def before_pay(self, request, pk):
        receipt = get_object_or_404(self.receipt_class, pk=pk)
        now = timezone.now()
        # bc = CouponConfig.get()
        # auto_cancel_minutes = bc.auto_cancel_minutes if bc else 5
        # expire_at = now + timedelta(minutes=-auto_cancel_minutes)
        order = receipt.coupon_receipt
        # receipt.query_status(order.order_no)
        # if receipt.paid:
        #     raise CustomAPIException('该订单已经付款，请尝试刷新订单页面')
        if order.status != order.STATUS_UNPAID:
            raise CustomAPIException('订单状态错误')
        # if order.create_at < expire_at:
        #     order.cancel()
        #     raise CustomAPIException('该订单支付过期，请重新下单')


class CouponOrderViewSet(ReturnNoneViewSet):
    queryset = CouponOrder.objects.all()
    serializer_class = CouponOrderSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def create_order(self, request):
        from concu.api_limit import try_queue, get_queue_size, get_max_wait
        with try_queue('coupon-order', get_queue_size(), get_max_wait()) as got:
            if got:
                s = CouponOrderCreateSerializer(data=request.data, context={'request': request})
                s.is_valid(True)
                order = s.create(s.validated_data)
            else:
                log.warning(f" can't the queue")
                raise CustomAPIException('手慢了，当前抢票人数较多，请稍后重试')
        return Response(data=dict(receipt_id=order.receipt.payno, pay_end_at=None))

    @action(methods=['get'], detail=False)
    def get_detail(self, request):
        order_no = request.GET.get('order_no')
        try:
            order = CouponOrder.objects.get(order_no=order_no, user_id=request.user.id)
            data = CouponOrderDetailSerializer(order, context={'request': request}).data
        except CouponOrder.DoesNotExist:
            raise Http404
        return Response(data)
