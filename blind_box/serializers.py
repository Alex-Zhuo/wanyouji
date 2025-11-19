# coding: utf-8
from __future__ import unicode_literals

import logging
from django.db.transaction import atomic
from rest_framework import serializers
from django.utils import timezone
import simplejson as json

from blind_box.models import (
    Prize, BlindBox, BlindBoxWinningRecord, WheelWinningRecord, WheelActivity, WheelSection,
    LotteryPurchaseRecord, PrizeDetailImage, BlindBoxCarouselImage, BlindBoxDetailImage, BlindBasic
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
    head_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Prize
        fields = PrizeSerializer.Meta.fields + ['detail_images', 'desc', 'instruction']


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
        fields = ['no', 'name', 'description', 'sections', 'config']


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
