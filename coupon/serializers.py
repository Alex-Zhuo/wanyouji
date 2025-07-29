# coding: utf-8
from __future__ import unicode_literals

import logging
from django.db.transaction import atomic
from rest_framework import serializers
from django.utils import timezone
import json
from coupon.models import Coupon, UserCouponRecord
from restframework_ext.exceptions import CustomAPIException
from ticket.models import ShowType, ShowProject

log = logging.getLogger(__name__)


class CouponShowTypesSerializer(serializers.ModelSerializer):
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')

    class Meta:
        model = ShowType
        fields = ['name', 'source_type_display']


class CouponShowsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowProject
        fields = ['title']


class CouponSerializer(serializers.ModelSerializer):
    is_upper_limit = serializers.SerializerMethodField()

    def get_is_upper_limit(self, obj):
        user = self.context.get('request').user
        obtain_num = UserCouponRecord.user_obtain_cache(obj.no, user.id)
        return obtain_num >= obj.user_obtain_limit if obj.user_obtain_limit > 0 else False

    class Meta:
        model = Coupon
        fields = ['name', 'no', 'amount', 'expire_time', 'user_tips', 'user_obtain_limit', 'require_amount',
                  'is_upper_limit']


class CouponDetailSerializer(CouponSerializer):
    limit_show_types = CouponShowTypesSerializer(many=True)
    shows = CouponShowsSerializer(many=True)

    class Meta:
        model = Coupon
        fields = CouponSerializer.Meta.fields + ['shows', 'limit_show_types']


class UserCouponRecordSerializer(serializers.ModelSerializer):
    snapshot = serializers.SerializerMethodField()
    order_no = serializers.SerializerMethodField()

    def get_order_no(self, obj):
        return obj.order.order_no if obj.order else None

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.snapshot)
        snapshot.pop('shows_ids', None)
        snapshot.pop('show_types_ids', None)
        return snapshot

    class Meta:
        model = UserCouponRecord
        fields = ['no', 'snapshot', 'status', 'expire_time', 'used_time', 'create_at', 'order_no', 'require_amount']


class UserCouponRecordCreateSerializer(serializers.ModelSerializer):
    no = serializers.CharField(required=True)

    class Meta:
        model = UserCouponRecord
        fields = ['no']

    @atomic
    def create(self, validated_data):
        user = self.context.get('request').user
        validated_data['user'] = user
        coupon = Coupon.objects.get(no=validated_data['no'])
        # if coupon.stock <= 0:
        #     raise CustomAPIException('数量不足')
        if coupon.status == Coupon.STATUS_OFF:
            raise CustomAPIException('消费券已下架')
        obtain_num = UserCouponRecord.user_obtain_cache(coupon.no, user.id)
        if coupon.user_obtain_limit > 0 and obtain_num >= coupon.user_obtain_limit:
            raise CustomAPIException('已达到领取上限')
        inst = UserCouponRecord.objects.create(user=user, coupon=coupon, expire_time=coupon.expire_time)
        inst.save_common()
        return inst


class UserCouponRecordAvailableSerializer(serializers.ModelSerializer):
    show_no = serializers.CharField(required=True)
    amount = serializers.DecimalField(required=True, max_digits=9, decimal_places=2)

    class Meta:
        model = UserCouponRecord
        fields = ['show_no', 'amount']

    @atomic
    def create(self, validated_data):
        res = []
        request = self.context.get('request')
        now_date = timezone.now().date()
        show_no = validated_data['show_no']
        amount = validated_data['amount']
        records = UserCouponRecord.objects.filter(user=request.user, status=UserCouponRecord.STATUS_DEFAULT,
                                                  expire_time__gte=now_date, require_amount__lte=amount)
        for record in records:
            coupon = record.coupon
            if not coupon.check_can_use():
                continue
            limit_show_types_list = list(coupon.limit_show_types.all().values_list('id', flat=True))
            if limit_show_types_list:
                from ticket.models import ShowProject
                try:
                    show = ShowProject.objects.get(no=show_no)
                except ShowProject.DoesNotExist:
                    raise CustomAPIException('找不到演出')
                if show.show_type.id not in limit_show_types_list:
                    continue
            limit_shows_list = list(coupon.shows.all().values_list('session_no', flat=True))
            if limit_shows_list and show_no not in limit_shows_list:
                continue
            res.append(record)
        return res
