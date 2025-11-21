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
    BlindReceipt, SR_GOOD, UserLotteryTimes, UserLotteryRecord, SR_COUPON
)
from restframework_ext.exceptions import CustomAPIException
from caches import get_redis_name, run_with_lock
from datetime import timedelta

log = logging.getLogger(__name__)


class PrizeOrderSerializer(serializers.ModelSerializer):
    rare_type_display = serializers.ReadOnlyField(source='get_rare_type_display')

    class Meta:
        model = Prize
        fields = ['head_image', 'rare_type_display', 'rare_type']


class PrizeSnapshotSerializer(serializers.ModelSerializer):
    rare_type_display = serializers.ReadOnlyField(source='get_rare_type_display')
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')
    head_image = serializers.SerializerMethodField()

    def get_head_image(self, obj):
        return obj.head_image.url

    class Meta:
        model = Prize
        fields = ['title', 'source_type', 'source_type_display', 'rare_type', 'no', 'desc', 'instruction',
                  'rare_type_display', 'amount', 'head_image']


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
        fields = ['no', 'prize', 'is_no_prize', 'thank_image', 'winning_tip']


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
        return dict(price=bl.price_per_lottery, rule=bl.wheel_rule, open_buy_times=bl.open_buy_times)

    class Meta:
        model = WheelActivity
        fields = ['no', 'name', 'description', 'sections', 'config', 'title_image', 'bg_image']


class BlindBoxOrderPrizeSerializer(serializers.ModelSerializer):
    prize = serializers.SerializerMethodField()

    def get_prize(self, obj):
        return PrizeOrderSerializer(obj.prize, context=self.context).data

    class Meta:
        model = BlindBoxWinningRecord
        fields = ['prize']


class WinningRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')
    snapshot = serializers.SerializerMethodField()
    query_express = serializers.SerializerMethodField()

    def get_snapshot(self, obj):
        request = self.context.get('request')
        snapshot = json.loads(obj.snapshot)
        head_image = snapshot.get('head_image', None)
        if head_image:
            snapshot['head_image'] = request.build_absolute_uri(head_image)
        else:
            snapshot['head_image'] = None
        quantity = snapshot.get('quantity', None)
        if not quantity:
            snapshot['quantity'] = 1
        return snapshot

    def get_query_express(self, obj):
        return obj.can_query_express

    class Meta:
        fields = ['no', 'source_type', 'source_type_display', 'status', 'status_display', 'snapshot', 'winning_at',
                  'query_express']


class WinningRecordDetailSerializer(WinningRecordSerializer):
    box = serializers.SerializerMethodField()

    def get_box(self, obj):
        order = obj.blind_box_order
        data = dict(title=obj.blind_box_title, order_no=None, amount=0,
                    box_no=obj.blind_box.no if obj.blind_box else None)
        if order:
            data['order_no'] = order.order_no
            data['amount'] = order.amount
        return data

    class Meta:
        fields = WinningRecordSerializer.Meta.fields + ['winning_at', 'receive_at', 'ship_at', 'complete_at',
                                                        'box', 'express_address', 'express_phone',
                                                        'express_user_name', 'express_company_name',
                                                        'express_no']


class BlindBoxWinningRecordSerializer(WinningRecordSerializer):
    class Meta:
        model = BlindBoxWinningRecord
        fields = WinningRecordSerializer.Meta.fields


class BlindBoxWinningRecordDetailSerializer(WinningRecordDetailSerializer):
    class Meta:
        model = BlindBoxWinningRecord
        fields = WinningRecordDetailSerializer.Meta.fields


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
                pay_end_at = timezone.now() + timedelta(minutes=auto_cancel_minutes)
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
                return receipt.payno, pay_end_at, order.order_no
            else:
                raise CustomAPIException('请不要太快下单，稍后再试')

    class Meta:
        model = BlindBoxOrder
        fields = ['amount', 'pay_type', 'box_no']


class BlindBoxWinningReceiveSerializer(serializers.ModelSerializer):
    no = serializers.CharField(required=True, help_text='中奖编号')
    address_id = serializers.IntegerField(required=True, help_text='用户地址ID')

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        key = get_redis_name('win_rc{}'.format(request.user.id))
        with run_with_lock(key, 3) as got:
            if got:
                try:
                    obj = BlindBoxWinningRecord.objects.get(no=validated_data['no'], user=user,
                                                            status=BlindBoxWinningRecord.ST_PENDING_RECEIVE)
                except BlindBoxWinningRecord.DoesNotExist:
                    raise CustomAPIException('找不到获奖记录,或已经领取过了')
                if obj.source_type != SR_GOOD:
                    raise CustomAPIException('该奖品类型不支持此操作')
                from mall.models import UserAddress
                try:
                    address = UserAddress.objects.get(pk=validated_data['address_id'], user=user)
                except UserAddress.DoesNotExist:
                    raise CustomAPIException('地址错误')
                obj.set_received(address)
            else:
                raise CustomAPIException('请勿重复领取')

    class Meta:
        model = BlindBoxWinningRecord
        fields = ['no', 'address_id']


class LotteryPurchaseRecordCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=9, decimal_places=2, required=True)
    pay_type = serializers.IntegerField(required=True)
    multiply = serializers.IntegerField(required=True)

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        if not user.mobile:
            raise CustomAPIException('请先绑定手机')
        key = get_redis_name('lottime_{}'.format(user.id))
        cb = BlindBasic.get()
        if not (cb and cb.open_buy_times):
            raise CustomAPIException('未开启配置')
        with run_with_lock(key, 5) as got:
            if got:
                real_amount = cb.price_per_lottery * validated_data['multiply']
                if real_amount != validated_data['amount']:
                    log.error('{},{}'.format(validated_data['amount'], real_amount))
                    raise CustomAPIException('购买失败，金额错误')
                from blind_box.models import WeiXinPayConfig
                wx_pay_config = WeiXinPayConfig.get_default()
                auto_cancel_minutes = cb.auto_cancel_minutes
                pay_end_at = timezone.now() + timedelta(minutes=auto_cancel_minutes)
                receipt = BlindReceipt.create_record(amount=real_amount, user=user,
                                                     pay_type=validated_data['pay_type'], biz=BlindReceipt.BIZ_LOTTERY,
                                                     wx_pay_config=wx_pay_config, pay_end_at=pay_end_at)
                validated_data['user'] = user
                validated_data['mobile'] = user.mobile
                validated_data['receipt'] = receipt
                validated_data['wx_pay_config'] = wx_pay_config
                validated_data['pay_end_at'] = pay_end_at
                LotteryPurchaseRecord.objects.create(**validated_data)
                return receipt.payno, pay_end_at
            else:
                raise CustomAPIException('请不要太快下单，稍后再试')

    class Meta:
        model = LotteryPurchaseRecord
        fields = ['amount', 'pay_type', 'multiply']


class WheelActivityDrawSerializer(serializers.ModelSerializer):
    no = serializers.CharField(required=True, help_text='转盘编号')

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        key = get_redis_name('wheeldw{}'.format(request.user.id))
        with run_with_lock(key, 3) as got:
            if got:
                try:
                    wheel_activity = WheelActivity.objects.get(no=validated_data['no'], status=WheelActivity.STATUS_ON)
                except WheelActivity.DoesNotExist:
                    raise CustomAPIException('转盘活动已结束！')
                ul = UserLotteryTimes.get_or_create_record(user)
                if ul.times <= 0:
                    raise CustomAPIException('抽奖次数不足')
                # 减了库存
                section = wheel_activity.draw_wheel_prize()
                if not section:
                    raise CustomAPIException('转盘活动已结束!！')
                else:
                    from blind_box.stock_updater import prsc
                    prize = section.prize
                    is_prize = True if (not section.is_no_prize) and prize else False
                    try:
                        lottery_record = UserLotteryRecord.create_record(user, wheel_activity, is_prize=is_prize)
                        if is_prize:
                            prize_snapshot = WheelWinningRecord.get_snapshot(prize)
                            ww = WheelWinningRecord.objects.create(lottery_record=lottery_record,
                                                                   wheel_activity=wheel_activity,
                                                                   wheel_name=wheel_activity.name, user=user,
                                                                   mobile=user.mobile, prize=prize,
                                                                   source_type=prize.source_type,
                                                                   snapshot=prize_snapshot,
                                                                   status=WheelWinningRecord.ST_PENDING_RECEIVE)
                            if prize.source_type == SR_COUPON:
                                # 发优惠卷
                                ww.send_coupon()
                        # 减次数
                        st = ul.update_times(-1, False)
                        if not st:
                            raise Exception('抽奖失败，减次数失败')
                    except Exception as e:
                        log.error(e)
                        if is_prize:
                            prsc.incr(prize.id, 1, ceiling=Ellipsis)
                            prsc.record_update_ts(prize.id)
                            log.info(f"已回滚奖品 {prize.id} 的库存")
                            raise CustomAPIException('抽奖失败，请稍后再试...')
                return section
            else:
                raise CustomAPIException('请勿重复领取')

    class Meta:
        model = WheelActivity
        fields = ['no']
