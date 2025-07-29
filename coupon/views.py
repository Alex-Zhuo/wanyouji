# coding:utf-8
from rest_framework import viewsets
from rest_framework.response import Response

from coupon.models import Coupon, UserCouponRecord
from coupon.serializers import CouponSerializer, UserCouponRecordSerializer, UserCouponRecordCreateSerializer, \
    UserCouponRecordAvailableSerializer
from home.views import ReturnNoDetailViewSet
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.mixins import SerializerSelector
from restframework_ext.pagination import StandardResultsSetPagination
from restframework_ext.permissions import IsPermittedUser
from rest_framework.decorators import action
from decimal import Decimal
from django.utils import timezone
from restframework_ext.exceptions import CustomAPIException


class CouponViewSet(ReturnNoDetailViewSet):
    queryset = Coupon.objects.filter(status=Coupon.STATUS_ON)
    permission_classes = [IsPermittedUser]
    serializer_class = CouponSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get']

    @action(methods=['post'], detail=False, http_method_names=['post'])
    def receive(self, request):
        s = UserCouponRecordCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()


class UserCouponRecordViewSet(ReturnNoDetailViewSet):
    queryset = UserCouponRecord.objects.all()
    serializer_class = UserCouponRecordSerializer
    permission_classes = [IsPermittedUser]
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    http_method_names = ['get', 'post']
    filter_fields = ['status']

    @action(methods=['post'], detail=False)
    def get_available(self, request):
        s = UserCouponRecordAvailableSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        res = s.create(s.validated_data)
        return Response(self.serializer_class(res, many=True, context={'request': request}).data)
