# coding=utf-8
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from blind_box.models import (
    Prize, BlindBox, BlindBoxWinningRecord, WheelWinningRecord, WheelActivity, LotteryPurchaseRecord
)
from blind_box.serializers import (
    PrizeSerializer, BlindBoxSerializer, WheelActivitySerializer,
    WinningRecordSerializer, LotteryPurchaseRecordSerializer
)
from blind_box.lottery_utils import draw_wheel_prize, draw_blind_box_prizes
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.permissions import IsPermittedUser
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.pagination import StandardResultsSetPagination
from home.views import ReturnNoDetailViewSet
from blind_box.stock_updater import prsc
import logging
import simplejson as json

log = logging.getLogger(__name__)


class PrizeViewSet(ReturnNoDetailViewSet):
    """奖品列表"""
    queryset = Prize.objects.filter(status=Prize.STATUS_ON)
    permission_classes = [IsPermittedUser]
    serializer_class = PrizeSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']


class BlindBoxViewSet(ReturnNoDetailViewSet):
    """盲盒列表"""
    queryset = BlindBox.objects.filter(status=BlindBox.STATUS_ON)
    permission_classes = [IsPermittedUser]
    serializer_class = BlindBoxSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['post'], detail=False)
    def check_stock(self, request):
        """检查盲盒库存和奖品池库存"""
        blind_box_id = request.data.get('blind_box_id')
        try:
            blind_box = BlindBox.objects.get(id=blind_box_id, status=BlindBox.STATUS_ON)
        except BlindBox.DoesNotExist:
            raise CustomAPIException('盲盒不存在或已下架')

        # 检查盲盒库存
        if blind_box.stock <= 0:
            raise CustomAPIException('盲盒库存不足，请稍后再试！')

        # 检查奖品池库存
        available_prizes = Prize.objects.filter(status=Prize.STATUS_ON)
        available_count = 0
        for prize in available_prizes:
            stock = prsc.get_stock(prize.id)
            if stock and int(stock) > 0:
                available_count += 1

        if available_count < blind_box.grids_num:
            raise CustomAPIException('奖品库存不足，请稍后再试！')

        return Response({'can_purchase': True})


class WheelActivityViewSet(ReturnNoDetailViewSet):
    """转盘活动列表"""
    queryset = WheelActivity.objects.filter(status=WheelActivity.STATUS_ON)
    permission_classes = [IsPermittedUser]
    serializer_class = WheelActivitySerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['post'], detail=True)
    def draw(self, request, pk=None):
        """转盘抽奖"""
        wheel_activity = self.get_object()
        user = request.user

        with transaction.atomic():
            winning_record = draw_wheel_prize(wheel_activity, user)
            if not winning_record:
                raise CustomAPIException('抽奖失败，请稍后重试')

        return Response(WinningRecordSerializer(winning_record, context={'request': request}).data)


class WinningRecordViewSet(ReturnNoDetailViewSet):
    """中奖记录"""
    queryset = WinningRecord.objects.all()
    permission_classes = [IsPermittedUser]
    serializer_class = WinningRecordSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    filter_fields = ['status', 'source_type']
    http_method_names = ['get', 'post', 'patch']

    @action(methods=['post'], detail=True)
    def receive(self, request, pk=None):
        """领取奖品（纸质票、券码类型）"""
        winning_record = self.get_object()

        if winning_record.source_type not in [Prize.SR_TICKET, Prize.SR_CODE]:
            raise CustomAPIException('该奖品类型不支持此操作')

        if winning_record.status != WinningRecord.ST_PENDING_RECEIVE:
            raise CustomAPIException('该中奖记录状态不正确')

        # 弹窗提示用户联系客服
        return Response({
            'message': '请联系在线客服提供中奖记录信息领取奖品！',
            'winning_no': winning_record.no
        })

    @action(methods=['post'], detail=True)
    def confirm_receipt(self, request, pk=None):
        """确认收货（实物奖品）"""
        winning_record = self.get_object()

        if winning_record.source_type != Prize.SR_GOOD:
            raise CustomAPIException('该奖品类型不支持此操作')

        if winning_record.status != WinningRecord.ST_PENDING_RECEIPT:
            raise CustomAPIException('该中奖记录状态不正确')

        winning_record.set_completed()
        return Response({'message': '确认收货成功'})


class LotteryPurchaseRecordViewSet(ReturnNoDetailViewSet):
    """抽奖次数购买记录"""
    queryset = LotteryPurchaseRecord.objects.all()
    permission_classes = [IsPermittedUser]
    serializer_class = LotteryPurchaseRecordSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    filter_fields = ['status', 'wheel_activity']
    http_method_names = ['get']
