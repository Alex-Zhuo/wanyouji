# coding: utf-8
from __future__ import unicode_literals

import logging
from django.db.transaction import atomic
from rest_framework import serializers
from django.utils import timezone
import simplejson as json

from blind_box.models import (
    Prize, BlindBox, BlindBoxWinningRecord, WheelWinningRecord, WheelActivity, WheelSection,
    LotteryPurchaseRecord, PrizeDetailImage, BlindBoxCarouselImage, BlindBoxDetailImage, BlindBasic, BlindBoxOrder,
    BlindReceipt
)
from restframework_ext.exceptions import CustomAPIException
from caches import get_redis_name, run_with_lock

log = logging.getLogger(__name__)


class PrizeSnapshotSerializer(serializers.ModelSerializer):
    rare_type_display = serializers.ReadOnlyField(source='get_rare_type_display')

    class Meta:
        model = Prize
        fields = ['title', 'rare_type', 'no', 'desc', 'instruction', 'rare_type_display', 'amount']


class PrizeDetailImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrizeDetailImage
        fields = ['image']


class PrizeSerializer(serializers.ModelSerializer):
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')
    rare_type_display = serializers.ReadOnlyField(source='get_rare_type_display')

    class Meta:
        model = Prize
        fields = ['no', 'title', 'head_image', 'source_type', 'source_type_display', 'rare_type', 'rare_type_display']


class PrizeDetailSerializer(PrizeSerializer):
    detail_images = PrizeDetailImageSerializer(many=True, read_only=True)

    class Meta:
        model = Prize
        fields = PrizeSerializer.Meta.fields + ['detail_images', 'desc', 'instruction', 'amount']


class BlindBoxCarouselImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlindBoxCarouselImage
        fields = ['image']


class BlindBoxDetailImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlindBoxDetailImage
        fields = ['image']


class BlindBoxSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    type_display = serializers.ReadOnlyField(source='get_type_display')
    grids_num_display = serializers.ReadOnlyField(source='get_grids_num_display')

    class Meta:
        model = BlindBox
        fields = ['no', 'title', 'status_display', 'status', 'grids_num', 'grids_num_display', 'type', 'type_display',
                  'price', 'original_price', 'logo']


class BlindBoxDetailSerializer(BlindBoxSerializer):
    carousel_images = BlindBoxCarouselImageSerializer(many=True, read_only=True)
    detail_images = BlindBoxDetailImageSerializer(many=True, read_only=True)
    config = serializers.SerializerMethodField()

    def get_config(self, obj):
        bl = BlindBasic.get()
        return dict(rule=bl.box_rule)

    class Meta:
        model = BlindBox
        fields = BlindBoxSerializer.Meta.fields + ['carousel_images', 'detail_images', 'desc', 'config']


class WheelSectionSerializer(serializers.ModelSerializer):
    prize = serializers.SerializerMethodField()

    def get_prize(self, obj):
        if not obj.prize:
            return None
        data = PrizeSerializer(obj.prize, context=self.context).data
        return data

    class Meta:
        model = WheelSection
        fields = ['no', 'prize', 'is_no_prize']


class WheelActivityBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = WheelActivity
        fields = ['name']


class WheelActivitySerializer(serializers.ModelSerializer):
    sections = serializers.SerializerMethodField()
    config = serializers.SerializerMethodField()

    def get_sections(self, obj):
        qs = obj.sections.filter(is_enabled=True)
        data = WheelSectionSerializer(qs, many=True, context=self.context).data
        return data

    def get_config(self, obj):
        bl = BlindBasic.get()
        return dict(price=bl.price_per_lottery, rule=bl.wheel_rule)

    class Meta:
        model = WheelActivity
        fields = ['no', 'name', 'description', 'sections', 'config', 'title_image', 'bg_image']


class WinningRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')
    source_display = serializers.ReadOnlyField(source='get_source_display')
    prize_title = serializers.SerializerMethodField()

    class Meta:
        model = BlindBoxWinningRecord
        fields = [
            'no', 'user', 'mobile', 'prize', 'prize_title', 'source_type', 'source_type_display',
            'instruction', 'status', 'status_display', 'express_no', 'express_company_code',
            'express_company_name', 'source', 'source_display', 'winning_at', 'receive_at',
            'ship_at', 'complete_at'
        ]

    def get_prize_title(self, obj):
        return obj.prize.title if obj.prize else ''


class LotteryPurchaseRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')

    class Meta:
        model = LotteryPurchaseRecord
        fields = [
            'order_no', 'user', 'mobile', 'wheel_activity', 'purchase_count', 'amount',
            'status', 'status_display', 'create_at'
        ]


class BlindBoxSnapshotSerializer(serializers.ModelSerializer):
    """盲盒快照序列化器"""
    type_display = serializers.ReadOnlyField(source='get_type_display')

    class Meta:
        model = BlindBox
        fields = ['no', 'title', 'type', 'type_display', 'grids_num', 'price', 'original_price', 'desc']


class BlindBoxOrderSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    snapshot = serializers.SerializerMethodField()

    def get_snapshot(self, obj):
        return json.loads(obj.snapshot)

    class Meta:
        model = BlindBoxOrder
        fields = ['order_no', 'amount', 'status', 'refund_amount', 'create_at', 'pay_at', 'status_display',
                  'pay_end_at', 'snapshot']


class BlindBoxOrderCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=9, decimal_places=2, required=True)
    box_no = serializers.CharField(required=True, help_text='盲盒编号')
    pay_type = serializers.IntegerField(required=True)

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        if not user.mobile:
            raise CustomAPIException('请先绑定手机')
        key = get_redis_name('blindorderc{}'.format(user.id))
        box_no = validated_data.pop('box_no')
        with run_with_lock(key, 20) as got:
            if got:
                try:
                    blind_box = BlindBox.objects.get(no=box_no, status=BlindBox.STATUS_ON)
                except BlindBox.DoesNotExist:
                    raise CustomAPIException('盲盒已下架')
                if blind_box.stock <= 0:
                    raise CustomAPIException('盲盒库存不足')
                real_amount = blind_box.price
                if real_amount != validated_data['amount']:
                    log.error('{},{}'.format(validated_data['amount'], real_amount))
                    raise CustomAPIException('下单失败，金额错误')

                validated_data['user'] = user
                validated_data['blind_box'] = blind_box
                validated_data['mobile'] = user.mobile
                validated_data['snapshot'] = BlindBoxOrder.get_snapshot(blind_box)
                from blind_box.models import WeiXinPayConfig
                wx_pay_config = WeiXinPayConfig.get_default()
                cb = BlindBasic.get()
                auto_cancel_minutes = cb.auto_cancel_minutes if cb else 5
                pay_end_at = timezone.now() + auto_cancel_minutes
                receipt = BlindReceipt.create_record(amount=real_amount, user=user,
                                                     pay_type=validated_data['pay_type'], biz=BlindReceipt.BIZ_BLIND,
                                                     wx_pay_config=wx_pay_config, pay_end_at=pay_end_at)
                validated_data['receipt'] = receipt
                validated_data['wx_pay_config'] = wx_pay_config
                validated_data['pay_end_at'] = pay_end_at
                order = BlindBoxOrder.objects.create(**validated_data)
                if not blind_box.blind_box_change_stock(-1):
                    raise CustomAPIException('盲盒库存不足')
                try:
                    prize_list = blind_box.draw_blind_box_prizes()
                    blind_win_list = []
                    prize_num = 0
                    for prize in prize_list:
                        prize_snapshot = BlindBoxWinningRecord.get_snapshot(prize)
                        blind_win_list.append(BlindBoxWinningRecord(blind_box_order=order, blind_box=blind_box,
                                                                    blind_box_title=blind_box.title, user=request.user,
                                                                    mobile=user.mobile, prize=prize,
                                                                    source_type=prize.source_type,
                                                                    snapshot=prize_snapshot))
                        prize_num += 1
                    if prize_num < blind_box.grids_num:
                        raise CustomAPIException(f"奖品库存不足，请稍后再试...")
                    if blind_win_list:
                        BlindBoxWinningRecord.objects.bulk_create(blind_win_list)
                except Exception as e:
                    # 盲盒库存回滚
                    blind_box.blind_box_change_stock(1)
                    raise CustomAPIException(str(e))
                return order
            else:
                raise CustomAPIException('请不要太快下单，稍后再试')

    class Meta:
        model = BlindBoxOrder
        fields = ['amount', 'pay_type', 'box_no']
