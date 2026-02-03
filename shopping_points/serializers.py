# coding: utf-8
from __future__ import unicode_literals
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import ModelSerializer
from rest_framework.serializers import ReadOnlyField, SerializerMethodField
from django.db.transaction import atomic
from rest_framework import serializers
import re
from express.models import Division
from mp.models import BasicConfig, ReturnAddress, DouYinImages
from shopping_points.models import UserAccountLevel, TransferBalanceRecord, UserCommissionMonthRecord
from shopping_points.models import CommissionWithdraw
from shopping_points.models import PointWithdraw
from shopping_points.models import UserAccount
from shopping_points.models import UserPointChangeRecord
from shopping_points.models import UserCommissionChangeRecord
from shopping_points.models import ReceiptAccount
from mp.models import ServiceConfig
from restframework_ext.exceptions import CustomAPIException
import logging

logger = logging.getLogger(__name__)


class UserAccountLevelSerializer(ModelSerializer):
    class Meta:
        model = UserAccountLevel
        fields = ['name', 'grade', 'slug', 'share_ratio', 'team_ratio']


# class UserAccountLevelSummarySerializer(ModelSerializer):
#     class Meta:
#         model = UserAccountLevel
#         fields = ('id', 'name', 'grade')


class CommissionWithdrawSerializer(ModelSerializer):
    status_display = ReadOnlyField(source='get_status_display')

    # @pysnooper.snoop(logger.debug)
    def is_valid(self, raise_exception=False):
        if super(CommissionWithdrawSerializer, self).is_valid(raise_exception):
            req = self.context.get('request')
            total, actual, fee = req.user.account.can_withdraw(self.validated_data['amount'])
            if actual != self.validated_data['amount']:
                raise CustomAPIException('提现金额错误')
            if fee != self.validated_data['fees']:
                raise CustomAPIException('手续费错误')
            # self.validated_data['fees'] = self.Meta.model.get_fees(self.validated_data['amount'])
            if self.validated_data['amount'] + self.validated_data['fees'] > req.user.user_account.commission_balance:
                raise ValidationError(dict(amount='金额超出'))
        return True

    # def is_valid(self, raise_exception=False):
    #     if super(CommissionWithdrawSerializer, self).is_valid(raise_exception):
    #         req = self.context.get('request')
    #         self.validated_data['fees'] = self.Meta.model.get_fees(self.validated_data['amount'])
    #         total = self.validated_data['fees'] + self.validated_data['amount']
    #         if total > req.user.user_account.commission_balance:
    #             raise ValidationError(dict(amount='可提现金额不足'))
    #         if total > 20000:
    #             raise ValidationError(dict(amount='单笔金额不能超过2W'))
    #         config = MallBaseConfig.get_base_config()
    #         withdraw_min = config.get('withdraw_min', 1)
    #         if self.validated_data['amount'] < Decimal(withdraw_min):
    #             raise ValidationError(dict(amount='单笔金额不能低于{}'.format(withdraw_min)))
    #     return True

    def create(self, validated_data):
        user = self.context.get('request').user
        logger.debug('validated_data: %s' % validated_data)
        inst = self.Meta.model.create(amount=validated_data['amount'], fees=validated_data['fees'],
                                      account=user.account)
        return inst

    class Meta:
        model = CommissionWithdraw
        fields = '__all__'
        read_only_fields = ['account', 'balance', 'create_at', 'approve_at', 'status', 'status_display']


class PointWithdrawSerializer(ModelSerializer):
    status_display = ReadOnlyField(source='get_status_display')

    def is_valid(self, raise_exception=False):
        if super(PointWithdrawSerializer, self).is_valid(raise_exception):
            req = self.context.get('request')
            if self.validated_data['amount'] > req.user.user_account.point_balance:
                raise ValidationError(dict(amount='积分超出'))
        return True

    def create(self, validated_data):
        return self.Meta.model.create(amount=validated_data['amount'],
                                      account=self.context.get('request').user.user_account,
                                      fees=0)

    class Meta:
        model = PointWithdraw
        fields = '__all__'
        read_only_fields = ['account', 'balance', 'create_at', 'approve_at', 'status', 'status_display']


class DivisionSerializer(ModelSerializer):
    class Meta:
        model = Division
        fields = ('province', 'city', 'county')


class UserAccountSerializer(ModelSerializer):
    level_name = ReadOnlyField()
    level_grade = SerializerMethodField()
    receipt_account = SerializerMethodField(read_only=True)
    can_share = SerializerMethodField()
    flag_display = ReadOnlyField(source='get_flag_display')
    manager_display = ReadOnlyField(source='get_manager_display')
    can_change_amount = SerializerMethodField()

    def get_can_change_amount(self, obj):
        return obj.can_change_amount()

    def get_receipt_account(self, obj):
        return []

    def get_level_grade(self, obj):
        return obj.level.grade if obj.level else 0

    def get_can_share(self, obj):
        return True

    class Meta:
        model = UserAccount
        fields = ['user', 'commission_balance', 'total_commission_balance', 'flag', 'manager', 'level', 'venue',
                  'level_name', 'level_grade', 'receipt_account', 'can_share', 'flag_display', 'manager_display',
                  'can_change_amount']


class UserPointChangeRecordSerializer(ModelSerializer):
    source_display = ReadOnlyField(source='get_source_type_display')
    status_display = ReadOnlyField(source='get_status_display')

    class Meta:
        model = UserPointChangeRecord
        fields = ['id', 'source_display', 'amount', 'desc', 'create_at', 'status_display']


class UserCommissionChangeRecordSerializer(ModelSerializer):
    order_user = SerializerMethodField()
    desc = SerializerMethodField()
    status_display = ReadOnlyField(source='get_status_display')
    mobile = SerializerMethodField()
    source_display = ReadOnlyField(source='get_source_type_display')
    order_info = SerializerMethodField()

    def get_order_info(self, obj):
        if obj.order:
            return dict(order_no=obj.order.order_no, name=str(obj.order.user), title=obj.order.title,
                        amount=obj.order.amount)
        return None

    def get_desc(self, obj):
        return obj.desc or obj.get_source_type_display()

    def get_order_user(self, obj):
        return '{}'.format(obj.order.user) if obj.order else ''

    def get_mobile(self, obj):
        return obj.account.user.mobile

    class Meta:
        model = UserCommissionChangeRecord
        fields = '__all__'


class UserCommissionMonthRecordSerializer(ModelSerializer):
    user_info = SerializerMethodField()

    def get_user_info(self, obj):
        user = obj.account.user
        if user.icon:
            avatar = self.context.get('request').build_absolute_uri(user.icon.url)
        else:
            avatar = user.avatar
        return dict(name=user.get_full_name(), avatar=avatar)

    class Meta:
        model = UserCommissionMonthRecord
        fields = '__all__'


class UserCommissionMonthRecordRankSerializer(ModelSerializer):
    user_info = SerializerMethodField()

    def get_user_info(self, obj):
        user = obj.account.user
        if user.icon:
            avatar = self.context.get('request').build_absolute_uri(user.icon.url)
        else:
            avatar = user.avatar
        return dict(name=user.get_full_name(), avatar=avatar)

    class Meta:
        model = UserCommissionMonthRecord
        fields = ['amount', 'user_info']


class ReceiptAccountSerializer(ModelSerializer):
    class Meta:
        model = ReceiptAccount
        fields = '__all__'
        read_only_fields = ['account']

    # def validate_account(self, value):
    #     return self.context.get('request').user.account

    def create(self, validated_data):
        validated_data['account'] = self.context.get('request').user.account
        inst = ReceiptAccount.objects.filter(account=validated_data['account']).first()
        if inst:
            for k, v in validated_data.iteritems():
                setattr(inst, k, v)
            inst.save()
            return inst
        return super(ReceiptAccountSerializer, self).create(validated_data)


class TransferBalanceRecordSerializer(ModelSerializer):

    def create(self, validated_data):
        user = self.context.get('request').user
        validated_data['source'] = user.user_account
        validated_data['to'] = user.parent.user_account if user.parent else None
        return self.Meta.model.create(**validated_data)

    class Meta:
        model = TransferBalanceRecord
        fields = ('amount',)


class TransferBalanceRecordDetailSerializer(ModelSerializer):
    source = SerializerMethodField()
    to = SerializerMethodField()
    is_out = SerializerMethodField()

    def get_is_out(self, obj):
        return obj.source.user == self.context.get('request').user

    def get_source(self, obj):
        return dict(last_name=obj.source.user.last_name, avatar=obj.source.user.avatar)

    def get_to(self, obj):
        if obj.to:
            return dict(last_name=obj.to.user.last_name, avatar=obj.to.user.avatar)
        else:
            return dict(last_name='平台')

    class Meta:
        model = TransferBalanceRecord
        fields = ('amount', 'source', 'to', 'create_at', 'status', 'confirm_at', 'is_out')


class UserBalanceTransferCreateSerializer(ModelSerializer):
    MOBILE_PATTERN = re.compile(r'1\d{10}')
    mobile = serializers.CharField(label='受赠人手机', max_length=11, min_length=11, write_only=True)

    def validate_mobile(self, value):
        from mall.models import User
        if not self.MOBILE_PATTERN.match(value):
            raise CustomAPIException('手机号格式错误')
        try:
            linkuser = User.objects.get(mobile=value)
            return linkuser.account
        except User.DoesNotExist:
            raise CustomAPIException('会员已到期或未找到，请查证后再重试。')

    def validate_amount(self, value):
        if value < 0:
            raise CustomAPIException('转赠消费金必须是正数')
        if value > self.context.get('request').user.account.point_balance:
            raise CustomAPIException('消费金不足')
        return value

    @atomic
    def create(self, validated_data):
        source_account = self.context.get('request').user.account
        to_account = validated_data['mobile']
        return UserPointChangeRecord.transfer(source_account, to_account, validated_data['amount'])

    class Meta:
        model = UserPointChangeRecord
        fields = ('amount', 'mobile')


class ServiceConfigSerializer(ModelSerializer):
    class Meta:
        model = ServiceConfig
        fields = '__all__'


class DivisionCreateSerializer(ModelSerializer):
    def run_validators(self, value):
        pass

    def create(self, validated_data):
        # for k, v in validated_data.items()[:]:
        #     if not v:
        #         validated_data.pop(k, None)
        # map(lambda k: validated_data.setdefault(k, None), ['city', 'county'])
        object, created = self.Meta.model.objects.get_or_create(**validated_data)
        # # 返回给外部看，是新建的对象还是更新
        # self.created = created
        return object

    class Meta:
        model = Division
        fields = ["province", "city", "county"]


class BasicConfigSerializer(ModelSerializer):
    dy_images = serializers.SerializerMethodField()

    def get_dy_images(self, obj):
        qs = DouYinImages.objects.all()
        return DouYinImagesSerializer(qs, many=True, context=self.context).data

    class Meta:
        model = BasicConfig
        fields = ['mall_name', 'wx_share_title', 'wx_share_desc', 'wx_share_img', 'venue_mobile', 'custom_work_at',
                  'service_agreement', 'realname_agreement', 'agent_agreement', 'platform_mobile', 'withdraw_min',
                  'business_img', 'dy_images', 'auto_cancel_minutes']


class ReturnAddressSerializer(ModelSerializer):
    class Meta:
        model = ReturnAddress
        fields = ['name', 'mobile', 'address']


class DouYinImagesSerializer(ModelSerializer):
    class Meta:
        model = DouYinImages
        fields = ['title', 'image']
