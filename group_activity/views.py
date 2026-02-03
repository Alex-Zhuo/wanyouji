# coding: utf-8
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import viewsets, views
from django.shortcuts import get_object_or_404
from group_activity.models import ActivityReceipt, ActivityConfig, GroupParticipantRefund
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.mixins import SerializerSelector
from restframework_ext.permissions import IsPermittedUser
from restframework_ext.pagination import StandardResultsSetPagination, DefaultNoPagePagination
import logging
from django.utils import timezone
from restframework_ext.views import BaseReceiptViewset
from datetime import timedelta

log = logging.getLogger(__name__)


class ActReceiptViewSet(BaseReceiptViewset):
    permission_classes = []
    receipt_class = ActivityReceipt
    refund_class = GroupParticipantRefund

    def before_pay(self, request, pk):
        receipt = get_object_or_404(self.receipt_class, pk=pk)
        now = timezone.now()
        bc = ActivityConfig.get()
        auto_cancel_minutes = bc.auto_cancel_minutes if bc else 5
        expire_at = now + timedelta(minutes=-auto_cancel_minutes)
        order = receipt.act_receipt
        receipt.query_status(order.order_no)
        if receipt.paid:
            raise CustomAPIException('该订单已经付款，请尝试刷新订单页面')
        if order.status != order.STATUS_UNPAID:
            raise CustomAPIException('订单状态错误')
        if order.create_at < expire_at:
            order.cancel()
            raise CustomAPIException('该订单支付过期，请重新下单')
        receipt.act_receipt.activity.check_can_payment()
