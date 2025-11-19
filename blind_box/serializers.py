# coding: utf-8
from __future__ import unicode_literals

import logging
from django.db.transaction import atomic
from rest_framework import serializers
from django.utils import timezone
import simplejson as json

from blind_box.models import (
    Prize, BlindBox, BlindBoxWinningRecord, WheelWinningRecord, WheelActivity, WheelSection,
    LotteryPurchaseRecord, PrizeDetailImage, BlindBoxCarouselImage, BlindBoxDetailImage
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
        fields = ['id', 'image']


class PrizeSerializer(serializers.ModelSerializer):
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')
    rare_type_display = serializers.ReadOnlyField(source='get_rare_type_display')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    detail_images = PrizeDetailImageSerializer(many=True, read_only=True)
    head_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Prize
        fields = [
            'no', 'title', 'head_image', 'head_image_url', 'source_type', 'source_type_display',
            'rare_type', 'rare_type_display', 'amount', 'desc', 'instruction', 'stock', 'weight',
            'status', 'status_display', 'create_at', 'detail_images'
        ]

    def get_head_image_url(self, obj):
        if obj.head_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.head_image.url)
        return None


class BlindBoxCarouselImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlindBoxCarouselImage
        fields = ['id', 'image']


class BlindBoxDetailImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlindBoxDetailImage
        fields = ['id', 'image']


class BlindBoxSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    type_display = serializers.ReadOnlyField(source='get_type_display')
    grids_num_display = serializers.ReadOnlyField(source='get_grids_num_display')
    carousel_images = BlindBoxCarouselImageSerializer(many=True, read_only=True)
    detail_images = BlindBoxDetailImageSerializer(many=True, read_only=True)
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = BlindBox
        fields = [
            'no', 'title', 'status', 'status_display', 'grids_num', 'grids_num_display',
            'type', 'type_display', 'price', 'original_price', 'stock', 'desc',
            'rare_weight_multiple', 'hidden_weight_multiple', 'logo', 'logo_url',
            'carousel_images', 'detail_images', 'create_at'
        ]

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
        return None


class WheelSectionSerializer(serializers.ModelSerializer):
    prize_name_display = serializers.SerializerMethodField()

    class Meta:
        model = WheelSection
        fields = ['id', 'prize', 'prize_name', 'prize_name_display', 'weight', 'winning_tip', 'is_enabled']

    def get_prize_name_display(self, obj):
        return obj.prize_name or (obj.prize.title if obj.prize else '')


class WheelActivityBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = WheelActivity
        fields = ['name']


class WheelActivitySerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    sections = WheelSectionSerializer(many=True, read_only=True)

    class Meta:
        model = WheelActivity
        fields = ['no', 'name', 'status', 'status_display', 'create_at', 'description', 'price_per_lottery', 'sections']


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
