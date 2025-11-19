# coding: utf-8
from __future__ import unicode_literals

import logging
from django.db.transaction import atomic
from rest_framework import serializers
from django.utils import timezone
import json
from coupon.models import Coupon, UserCouponRecord, CouponActivity, CouponOrder, CouponReceipt, CouponBasic
from restframework_ext.exceptions import CustomAPIException
from ticket.models import ShowType, ShowProject
from caches import get_redis_name, run_with_lock

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


class CouponBasicSerializer(serializers.ModelSerializer):
    type_display = serializers.ReadOnlyField(source='get_type_display')

    class Meta:
        model = Coupon
        fields = ['name', 'no', 'amount', 'discount', 'expire_time', 'user_tips', 'require_amount',
                  'require_num', 'type', 'type_display']


class CouponSerializer(CouponBasicSerializer):
    is_upper_limit = serializers.SerializerMethodField()
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')
    need_buy = serializers.SerializerMethodField()

    def get_is_upper_limit(self, obj):
        st = False
        if not obj.need_buy:
            user = self.context.get('request').user
            if obj.user_obtain_limit > 0:
                # obtain_num = user.coupons.filter(coupon_id=obj.id).count()
                obtain_num = UserCouponRecord.get_user_obtain_cache(obj.no, user.id)
                st = obtain_num >= obj.user_obtain_limit
        return st

    def get_need_buy(self, obj):
        return obj.need_buy

    class Meta:
        model = Coupon
        fields = CouponBasicSerializer.Meta.fields + ['is_upper_limit', 'user_obtain_limit', 'source_type',
                                                      'source_type_display',
                                                      'pay_amount', 'need_buy']


class CouponDetailSerializer(CouponSerializer):
    limit_show_types = CouponShowTypesSerializer(many=True)
    shows = CouponShowsSerializer(many=True)

    class Meta:
        model = Coupon
        fields = CouponSerializer.Meta.fields + ['shows', 'limit_show_types']


class UserCouponRecordSerializer(serializers.ModelSerializer):
    snapshot = serializers.SerializerMethodField()

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.snapshot)
        snapshot.pop('shows_ids', None)
        snapshot.pop('show_types_ids', None)
        return snapshot

    class Meta:
        model = UserCouponRecord
        fields = ['no', 'snapshot', 'status', 'expire_time', 'used_time', 'create_at', 'amount', 'discount',
                  'require_amount', 'require_num', 'coupon_type']


class UserCouponRecordCreateSerializer(serializers.ModelSerializer):
    no = serializers.CharField(required=True)

    class Meta:
        model = UserCouponRecord
        fields = ['no']

    @atomic
    def create(self, validated_data):
        user = self.context.get('request').user
        validated_data['user'] = user
        try:
            coupon = Coupon.objects.get(no=validated_data['no'])
        except Coupon.DoesNotExist:
            raise CustomAPIException('消费卷不存在')
        if coupon.stock <= 0:
            raise CustomAPIException('消费券库存不足')
        if coupon.status == Coupon.STATUS_OFF:
            raise CustomAPIException('消费券已下架')
        obtain_num = UserCouponRecord.get_user_obtain_cache(coupon.no, user.id)
        # obtain_num = user.coupons.filter(coupon_id=coupon.id).count()
        if coupon.user_obtain_limit > 0 and obtain_num >= coupon.user_obtain_limit:
            raise CustomAPIException('已达到领取上限')
        inst = UserCouponRecord.create_record(user.id, coupon)
        st = coupon.coupon_change_stock(-1)
        if not st:
            raise CustomAPIException('消费券库存不足')
        return inst


# class UserCouponRecordAvailableSerializer(serializers.ModelSerializer):
#     show_no = serializers.CharField(required=True)
#     amount = serializers.DecimalField(required=True, max_digits=9, decimal_places=2)
#
#     class Meta:
#         model = UserCouponRecord
#         fields = ['show_no', 'amount']
#
#     def create(self, validated_data):
#         res = []
#         request = self.context.get('request')
#         now_date = timezone.now().date()
#         show_no = validated_data['show_no']
#         amount = validated_data['amount']
#         # log.error(validated_data)
#         # log.error(request.user.id)
#         records = UserCouponRecord.objects.filter(user=request.user, status=UserCouponRecord.STATUS_DEFAULT,
#                                                   expire_time__gte=now_date, require_amount__lte=amount)
#         for record in records:
#             coupon = record.coupon
#             if not coupon.check_can_use():
#                 continue
#             from ticket.models import ShowProject
#             try:
#                 show = ShowProject.objects.get(no=show_no)
#             except ShowProject.DoesNotExist:
#                 raise CustomAPIException('找不到演出')
#             can_use = record.check_can_show_use(show)
#             if can_use:
#                 res.append(record)
#         return res


class UserCouponRecordAvailableNewSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(required=True, max_digits=9, decimal_places=2)
    show_no = serializers.CharField(required=True)
    multiply = serializers.IntegerField(required=True)

    class Meta:
        model = UserCouponRecord
        fields = ['show_no', 'amount', 'multiply']

    def create(self, validated_data):
        res = []
        if validated_data['amount'] <= 0:
            return res
        request = self.context.get('request')
        now_date = timezone.now().date()
        show_no = validated_data['show_no']
        amount = validated_data['amount']
        multiply = validated_data['multiply']
        from ticket.models import ShowProject
        try:
            show = ShowProject.objects.get(no=show_no)
        except ShowProject.DoesNotExist:
            raise CustomAPIException('找不到演出')
        records = UserCouponRecord.objects.filter(user=request.user, status=UserCouponRecord.STATUS_DEFAULT,
                                                  expire_time__gte=now_date)
        for record in records:
            coupon = record.coupon
            if not coupon.check_can_use():
                continue
            can_use = record.coupon_check_can_use(show, amount, multiply)
            if can_use:
                res.append(record)
        return res


class CouponActivitySerializer(serializers.ModelSerializer):
    coupons = CouponBasicSerializer(many=True)

    class Meta:
        model = CouponActivity
        fields = ['no', 'title', 'coupons', 'share_img', 'status']


class UserCouponRecordActCreateSerializer(serializers.ModelSerializer):
    act_no = serializers.CharField(required=True)

    class Meta:
        model = UserCouponRecord
        fields = ['act_no']

    @atomic
    def create(self, validated_data):
        user = self.context.get('request').user
        validated_data['user'] = user
        # log.error(validated_data['act_no'])
        try:
            act = CouponActivity.objects.get(no=validated_data['act_no'])
        except CouponActivity.DoesNotExist:
            raise CustomAPIException('活动不存在')
        if act.status == CouponActivity.ST_OFF:
            raise CustomAPIException('活动已结束')
        coupon_list = act.coupons.all()
        success = 0
        for coupon in coupon_list:
            if coupon.stock <= 0:
                continue
            obtain_num = UserCouponRecord.get_user_obtain_cache(coupon.no, user.id)
            if coupon.user_obtain_limit > 0 and obtain_num >= coupon.user_obtain_limit:
                continue
            if not coupon.coupon_change_stock(-1):
                continue
            try:
                UserCouponRecord.create_record(user.id, coupon)
            except Exception as e:
                log.error(e)
                # 领取出错加回去数量
                coupon.coupon_change_stock(1)
                continue
            success += 1
        # 有一条领取成功则算成功
        if success <= 0:
            raise CustomAPIException('已抢光！')


class CouponOrderSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    coupon_data = serializers.SerializerMethodField()

    def get_coupon_data(self, obj):
        data = None
        if hasattr(obj, 'buy_order'):
            data = UserCouponRecordSerializer(obj.buy_order, context=self.context).data
        return data

    class Meta:
        model = CouponOrder
        fields = ['order_no', 'amount', 'status', 'multiply', 'create_at', 'pay_at', 'status_display', 'coupon_data',
                  'pay_end_at']


class CouponOrderDetailSerializer(CouponOrderSerializer):
    class Meta:
        model = CouponOrder
        fields = CouponOrderSerializer.Meta.fields


class CouponOrderCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=9, decimal_places=2, required=True)
    coupon_no = serializers.CharField(required=True, help_text='消费卷号')
    pay_type = serializers.IntegerField(required=True)
    multiply = serializers.IntegerField(required=True)

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        if not user.mobile:
            raise CustomAPIException('请先绑定手机')
        if validated_data['multiply'] != 1:
            raise CustomAPIException('每次最多购买一张')
        key = get_redis_name('cnpod_{}'.format(user.id))
        coupon_no = validated_data.pop('coupon_no')
        with run_with_lock(key, 5) as got:
            if got:
                try:
                    coupon = Coupon.objects.get(no=coupon_no, status=Coupon.STATUS_ON, source_type=Coupon.SR_PAY)
                except Coupon.DoesNotExist:
                    raise CustomAPIException('消费卷已下架')
                obtain_num = UserCouponRecord.get_user_obtain_cache(coupon.no, user.id)
                # obtain_num = user.coupons.filter(coupon_id=coupon.id).count()
                if coupon.user_obtain_limit > 0 and obtain_num >= coupon.user_obtain_limit:
                    raise CustomAPIException('消费券已达到购买上限')
                if coupon.pay_amount == 0:
                    raise CustomAPIException('消费券可免费领取')
                if coupon.stock <= 0:
                    raise CustomAPIException('消费券库存不足')
                real_amount = coupon.pay_amount * validated_data['multiply']
                if real_amount != validated_data['amount']:
                    log.error('{},{}'.format(validated_data['amount'], real_amount))
                    raise CustomAPIException('下单失败，金额错误')
                validated_data['coupon'] = coupon
                validated_data['user'] = user
                validated_data['mobile'] = user.mobile
                # validated_data['snapshot'] = CouponOrder.get_snapshot(coupon)
                from mp.models import WeiXinPayConfig
                wx_pay_config = WeiXinPayConfig.get_default()
                cb = CouponBasic.get()
                auto_cancel_minutes = cb.auto_cancel_minutes if cb else 5
                pay_end_at = timezone.now() + auto_cancel_minutes
                receipt = CouponReceipt.create_record(amount=real_amount, user=user,
                                                      pay_type=validated_data['pay_type'], biz=CouponReceipt.BIZ_ACT,
                                                      wx_pay_config=wx_pay_config, pay_end_at=pay_end_at)
                validated_data['receipt'] = receipt
                validated_data['wx_pay_config'] = wx_pay_config
                validated_data['coupon_name'] = coupon.name
                validated_data['pay_end_at'] = pay_end_at
                order = CouponOrder.objects.create(**validated_data)
                if not coupon.coupon_change_stock(-validated_data['multiply']):
                    raise CustomAPIException('消费券库存不足')
                return order
            else:
                raise CustomAPIException('请不要太快下单，稍后再试')

    class Meta:
        model = CouponOrder
        fields = ['amount', 'pay_type', 'coupon_no', 'multiply']
