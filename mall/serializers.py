# coding: utf-8
from __future__ import unicode_literals

import logging
from django.db.transaction import atomic
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import CharField
from django.utils import timezone

from renovation.models import ResourceImageItem, Resource
from mp.models import ShareQrcodeBackground
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.serializers import FormatExceptionMixin
from shopping_points.models import UserAccount
from qcloud.consts import VrKeys
from qcloud.serializers import VerificationCodeMixin
from shopping_points.serializers import DivisionSerializer
from .models import User, HotSearch, ExpressCompany, ServiceAuthRecord, MembershipCard, MembershipImage, \
    MemberCardRecord, CardRecord, AgreementRecord, TheaterCard, TheaterCardTicketLevel, TheaterCardCity, \
    TheaterCardImage, TheaterCardOrder, TheaterCardUserRecord, TheaterCardUserBuy, TheaterCardChangeRecord, UserAddress, \
    TheaterCardUserDetail
from express.models import Division
from mall.models import SubPages
from common.config import get_config
from decouple import config

logger = logging.getLogger(__name__)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    level_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

    def get_last_name(self, obj):
        return obj.last_name or obj.username

    def get_avatar(self, obj):
        if obj.icon:
            return self.context.get('request').build_absolute_uri(obj.icon.url)
        else:
            return obj.avatar

    def get_level_name(self, obj):
        return obj.account.level.name if obj.account.level else None

    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name', 'mobile', 'avatar', 'level_name', 'follow', 'date_joined')


class UserInfoSerializer(serializers.ModelSerializer):
    nickname = serializers.ReadOnlyField(source='get_full_name')
    subscribe = serializers.ReadOnlyField(source='follow')
    level = serializers.SerializerMethodField(read_only=True)
    extra = serializers.SerializerMethodField(label='配置信息')
    has_location = serializers.SerializerMethodField(label='has_location')
    parent = serializers.SerializerMethodField()
    card_deadline = serializers.SerializerMethodField()
    theater_card_amount = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    token = serializers.SerializerMethodField()

    def get_token(self, obj):
        from restframework_ext.permissions import get_token
        request = self.context.get('request')
        return get_token(request)

    def get_avatar(self, obj):
        if obj.icon:
            return self.context.get('request').build_absolute_uri(obj.icon.url)
        else:
            return obj.avatar

    def get_theater_card_amount(self, obj):
        tc_card = TheaterCardUserRecord.objects.filter(user=obj).first()
        return tc_card.amount if tc_card else 0

    def get_card_deadline(self, obj):
        inst = CardRecord.objects.filter(user=obj).first()
        return inst.deadline_at if inst and inst.deadline_at and inst.deadline_at >= timezone.now().date() else None

    class Meta:
        model = get_user_model()
        fields = ('avatar', 'subscribe', 'first_name', 'last_name', 'token', 'nickname', 'share_code',
                  'icon', 'mobile', 'level', 'extra', 'has_location', 'card_deadline',
                  'parent', 'province', 'city', 'county', 'iv', 'flag', 'theater_card_amount')

    def get_parent(self, obj):
        if obj.parent_id:
            return dict(last_name=obj.parent.last_name, mobile=obj.parent.mobile, wechat=obj.parent.wechat)

    def get_has_location(self, obj):
        if obj.province:
            return 1
        else:
            return 0

    def get_extra(self, obj):
        # approve = 1代表小程序在审核
        return dict(approve=1)

    def get_level(self, obj):
        return None
        # return obj.user_account.level_id


class UserInfoNewSerializer(serializers.ModelSerializer):
    nickname = serializers.ReadOnlyField(source='get_full_name')
    subscribe = serializers.ReadOnlyField(source='follow')
    avatar = serializers.SerializerMethodField()
    token = serializers.SerializerMethodField()
    uid = serializers.SerializerMethodField()

    def get_uid(self, obj):
        return obj.get_share_code()

    def get_token(self, obj):
        if obj.check_and_update_day_visit_at():
            from blind_box.models import UserLotteryTimesDetail
            UserLotteryTimesDetail.add_record(obj, times=1, source_type=UserLotteryTimesDetail.SR_LOGIN,
                                              add_total=True)
        from restframework_ext.permissions import get_token
        request = self.context.get('request')
        return get_token(request)

    def get_avatar(self, obj):
        if obj.icon:
            return self.context.get('request').build_absolute_uri(obj.icon.url)
        else:
            return obj.avatar

    class Meta:
        model = get_user_model()
        fields = ['avatar', 'subscribe', 'first_name', 'last_name', 'token', 'nickname', 'share_code', 'mobile',
                  'flag', 'uid', 'agree_member', 'agree_privacy', 'agree_agent']


class UserInfoCacheSerializer(serializers.ModelSerializer):
    nickname = serializers.ReadOnlyField(source='get_full_name')
    subscribe = serializers.ReadOnlyField(source='follow')
    avatar = serializers.SerializerMethodField()
    uid = serializers.SerializerMethodField()

    def get_uid(self, obj):
        return obj.get_share_code()

    def get_avatar(self, obj):
        if obj.icon:
            return obj.icon.url
        else:
            return obj.avatar

    class Meta:
        model = get_user_model()
        fields = ['avatar', 'subscribe', 'first_name', 'last_name', 'nickname', 'share_code', 'mobile',
                  'flag', 'uid', 'agree_member', 'agree_privacy', 'agree_agent']


class SetUserMobileSerializer(serializers.ModelSerializer):
    def validate_mobile(self, value):
        if User.objects.filter(mobile=value).exclude(id=self.instance.id).exists():
            raise CustomAPIException('手机号码已经存在')
        return value

    def validate_wechat(self, value):
        if User.objects.filter(wechat=value).exclude(id=self.instance.id).exists():
            raise CustomAPIException('微信号已经存在')
        return value

    class Meta:
        model = User
        fields = ('mobile', 'wechat')


class UserAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['level']
        depth = 1


class FriendsSerializer(serializers.ModelSerializer):
    user_account = UserAccountSerializer(many=False, read_only=True)
    last_name = serializers.SerializerMethodField(read_only=True)

    def get_last_name(self, obj):
        user = self.context.get('request').user
        if not obj.path.startswith(user.path):
            return '%s(平推)' % obj.last_name
        else:
            return obj.last_name

    class Meta:
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'date_joined', 'avatar', 'user_account')


class UserForgetPasswordSerializer(serializers.ModelSerializer):
    username = CharField(label=u'手机号', max_length=150)

    def validate_username(self, value):
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist:
            raise ValidationError(u'用户找不到')

    class Meta:
        model = get_user_model()
        fields = ('username', 'password')


class UserRegisterSerializer(FormatExceptionMixin, VerificationCodeMixin, serializers.ModelSerializer):
    vr = CharField(write_only=True)
    mobile = serializers.CharField(required=True)
    # nation_code = serializers.CharField(required=False)
    password = serializers.CharField(required=False, label='密码', error_messages={
        'required': _('请填写密码'),
        'null': _('请填写密码')
    })
    parent = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    vrcode_key = VrKeys.vr

    def validate_mobile(self, value):
        if not value:
            raise CustomAPIException('手机号不能为空')
        super(UserRegisterSerializer, self).validate_mobile(value)
        return value

    def validate_password(self, value):
        if value and len(value) >= 6:
            return value
        raise CustomAPIException(u'密码长度不能少于6位')

    def validate_parent(self, value):
        if value:
            try:
                parent = User.objects.get(mobile=value)
            except User.DoesNotExist:
                raise CustomAPIException('未找到上级用户, 请检查ID')
            if not parent.has_paid_order and not parent.user_account.level:
                raise CustomAPIException('上级不满足条件，不能绑定')
            return parent

    class Meta:
        model = get_user_model()
        fields = ('username', 'password', 'mobile', 'vr', 'parent')
        read_only_fields = ('username',)

    @transaction.atomic
    def create(self, validated_data):
        validated_data['username'] = validated_data['mobile']
        validated_data['password'] = make_password(validated_data['password'])
        validated_data.pop('vr', None)
        try:
            user = User.objects.get(mobile=validated_data['mobile'])
            raise CustomAPIException('该手机号已经注册，请登录')
        except User.DoesNotExist:
            user = User.objects.create(last_name=validated_data.get('mobile'), **validated_data)
        return user


class UserChangePwdSerializer(serializers.ModelSerializer):
    password_old = serializers.CharField(required=True)
    password_new = serializers.CharField(required=True)

    def validate(self, attrs):
        user = authenticate(username=self.context.get('request').user.username, password=attrs.get('password_old'))
        if user:
            return attrs
        else:
            raise ValidationError('当前密码不正确')

    class Meta:
        model = get_user_model()
        fields = ('password_old', 'password_new')


class UserAddressSerMixin(serializers.ModelSerializer):
    show_express_address = serializers.SerializerMethodField()

    def get_show_express_address(self, useraddress):
        return ''.join(
            [useraddress.province, useraddress.city, useraddress.county, useraddress.street or '', useraddress.address])

    class Meta:
        model = UserAddress
        fields = ['show_express_address']


class UserAddressCreateSerializer(UserAddressSerMixin):
    class Meta:
        model = UserAddress
        fields = ['phone', 'default', 'province', 'city', 'county', 'address', 'receive_name', 'street', 'id',
                  'show_express_address']

    def validate_address(self, value):
        """

        :param value:
        :return:
        """
        return value.replace('#', '号')

    def check_if_default(self, validated_data):
        if validated_data.get('default'):
            UserAddress.objects.filter(user_id=self.context.get('request').user.id).update(default=False)

    def fix_get_city_by_prov_and_county(self, validated_data):
        """
        通过省和区县 查询所在市
        :param validated_data:
        :return:
        """
        if validated_data['city'] == validated_data['province']:
            city = Division.objects.filter(province=validated_data['province'],
                                           county=validated_data['county']).values_list('city', flat=True).first()
            if city:
                validated_data['city'] = city
                logger.error("find city:%s by %s, %s" % (city, validated_data['province'], validated_data['county']))
            else:
                logger.error("can't find city by %s, %s" % (validated_data['province'], validated_data['county']))

    def create(self, validated_data):
        self.check_if_default(validated_data)
        self.fix_get_city_by_prov_and_county(validated_data)
        validated_data['user'] = self.context.get('request').user

        return super(UserAddressCreateSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        self.check_if_default(validated_data)
        self.fix_get_city_by_prov_and_county(validated_data)
        validated_data['user'] = self.context.get('request').user
        return super(UserAddressCreateSerializer, self).update(instance, validated_data)


class UserAddressSerializer(serializers.ModelSerializer):
    show_express_address = serializers.SerializerMethodField()

    def get_show_express_address(self, useraddress):
        return ''.join(
            [useraddress.province, useraddress.city, useraddress.county, useraddress.street or '', useraddress.address])

    class Meta:
        model = UserAddress
        fields = ['id', 'show_express_address', 'phone', 'default', 'province', 'city', 'county', 'address',
                  'receive_name', 'street']


class HotSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotSearch
        fields = '__all__'


class SubPagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubPages
        fields = ['page_name', 'page_code', 'share_desc', 'share_image']


class BaseUserInfoSerializer(serializers.ModelSerializer):
    nickname = serializers.ReadOnlyField(source='get_full_name')
    level = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ('nickname', 'avatar', 'level')

    def get_level(self, obj):
        return obj.user_account.level.name if obj.user_account.level else ''


class SetUserLocationSerializer(serializers.ModelSerializer):

    def update(self, instance, validated_data):
        try:
            return super(SetUserLocationSerializer, self).update(instance, validated_data)
        finally:
            if not instance.parent:
                instance.auto_assign_consultant()

    class Meta:
        model = User
        fields = ('province', 'city', 'county', 'coordinates')


class ExpressCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpressCompany
        fields = ('code', 'name', 'id')


class ResourceItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url) if obj.image else None

    class Meta:
        model = ResourceImageItem
        fields = ['url', 'image']


class ResourceSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    def get_items(self, obj):
        request = self.context.get('request')
        if request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok':
            items = ResourceImageItem.objects.filter(resource_id=obj.id, is_dy_show=True)
        else:
            items = ResourceImageItem.objects.filter(resource_id=obj.id)
        return ResourceItemSerializer(items, many=True, context=self.context).data

    class Meta:
        model = Resource
        fields = ['code', 'name', 'status', 'items']


class CaptchaSerializer(serializers.ModelSerializer):
    reqid = serializers.CharField(write_only=True, required=True, max_length=30, min_length=10)
    mobile = serializers.CharField(required=True)

    def validate_mobile(self, value):
        import re
        REG_MOBILE = r'^\d{11}$'
        R_MOBILE = re.compile(REG_MOBILE)
        if not R_MOBILE.match(value):
            raise CustomAPIException('手机号格式不对')
        return value

    class Meta:
        model = get_user_model()
        fields = ['mobile', 'reqid']


class SmsCodeSerializer(serializers.ModelSerializer):
    reqid = serializers.CharField(write_only=True, required=True, max_length=30, min_length=10)
    mobile = serializers.CharField(required=True)
    imgrand = serializers.CharField(write_only=True, required=False, max_length=6, min_length=2, allow_blank=True,
                                    allow_null=True)

    class Meta:
        model = get_user_model()
        fields = ['mobile', 'imgrand', 'reqid']


class Stricth5UserRegisterSerializer(serializers.ModelSerializer):
    vr = CharField(write_only=True)
    mobile = serializers.CharField(required=True)
    imgrand = serializers.CharField(write_only=True, required=False, max_length=6, min_length=2, allow_blank=True,
                                    allow_null=True)
    reqid = serializers.CharField(write_only=True, max_length=30, min_length=6)
    password = serializers.CharField(required=False, label='密码', error_messages={
        'required': _('请填写密码'),
        'null': _('请填写密码')
    })
    share_code = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = get_user_model()
        fields = ('mobile', 'vr', 'imgrand', 'reqid', 'password', 'share_code')

    # def validate_username(self, value):
    #     if is_contains_chinese(unicode(value)):
    #         raise CustomAPIException(u'用户名不能有中文和空格')
    #     else:
    #         return value

    def validate_password(self, value):
        if value and len(value) >= 6:
            return value
        raise CustomAPIException(u'密码长度不能少于6位')

    # @pysnooper.snoop(logger.debug)
    def validate_request(self, validated_data):
        """
        检查验证码, 考虑复杂与简单模式
        :param validated_data:
        :return:
        """
        from caches import with_redis
        imgrand = validated_data.get('imgrand')
        if imgrand:
            key = self.get_send_sms_code_key(validated_data)
        else:
            key = self.get_send_sms_code_key_simple(validated_data)
        with with_redis() as redis:
            expect = redis.get(key)
            if expect is None:
                raise CustomAPIException('验证码过期', 2)
            if expect != validated_data['vr']:
                raise CustomAPIException('验证码错误')

    def get_send_sms_code_key(self, validated_data):
        """
        短信的key -> 验证码
        :param reqid:
        :param mobile:
        :param imgrand:
        :return:
        """
        '新的配置'
        data = dict()
        data['key_prefix'] = config('prefix')
        conf = get_config()
        data['key_prefix'] = conf.get('redis').get('prefix')
        data['mobile'] = validated_data['mobile']
        data['imgrand'] = validated_data.pop('imgrand')
        return '{key_prefix}:sms:1:{reqid}:{mobile}:{imgrand}'.format(**data)

    def get_send_sms_code_key_simple(self, validated_data):
        """
        短信的key -> 验证码
        :param reqid:
        :param mobile:
        :param imgrand:
        :return:
        """

        data = dict()
        conf = get_config()
        data['key_prefix'] = conf.get('redis').get('prefix')
        data['reqid'] = validated_data.pop('reqid')
        validated_data.pop('imgrand')
        data['mobile'] = validated_data['mobile']
        return '{key_prefix}:sms:0:{reqid}:{mobile}'.format(**data)

    @transaction.atomic
    def create(self, validated_data):
        from django.contrib.auth.hashers import make_password
        # logger.debug(validated_data)
        self.validate_request(validated_data)
        try:
            u = User.objects.get(mobile=validated_data['mobile'])
            if u:
                raise CustomAPIException('该手机号已经注册过了')
        except User.DoesNotExist:
            validated_data['password'] = make_password(validated_data['password'])
            validated_data.pop('vr', None)
            share_code = validated_data.pop('share_code', None)
            validated_data['username'] = validated_data['last_name'] = validated_data['mobile']
            user = User.objects.create(**validated_data)
            if share_code:
                try:
                    parent = User.objects.get(mobile=share_code)
                    if user and parent:
                        user.bind_parent(parent=parent)
                except User.MultipleObjectsReturned:
                    logger.warning("find multiple object by %s" % share_code)
                except User.DoesNotExist:
                    pass
            from rest_framework.response import Response
            resp = Response()
            user.login_user(self.context.get('request'), resp)
            # 注册赠送级别
            #  user.account.regist_level()
            return user


class UserForgetpasswordSerializer(Stricth5UserRegisterSerializer):
    @transaction.atomic
    def create(self, validated_data):
        self.validate_request(validated_data)
        try:
            user = User.objects.filter(mobile=validated_data['mobile'], username=validated_data['username']).get()
            user.set_password(validated_data['password'])
            user.save(update_fields=['password'])
            return user
        except User.DoesNotExist:
            raise CustomAPIException('该手机号和账号匹配不上')


class UserSetMobileSerializer(Stricth5UserRegisterSerializer):
    first_name = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        self.validate_request(validated_data)
        user = request.user
        user = user.combine_user(validated_data['mobile'], request=request, source_type=2,
                                 first_name=validated_data.get('first_name'))
        return user

    class Meta:
        model = get_user_model()
        fields = ['mobile', 'vr', 'imgrand', 'reqid', 'first_name']


class ShareQrcodeBackgroundSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareQrcodeBackground
        fields = ('id', 'image')


class ServiceAuthRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceAuthRecord
        fields = ['auth_type', 'create_at']


class MembershipImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        from common.config import get_config
        config = get_config()
        return '{}{}'.format(config['template_url'], obj.image.url)

    class Meta:
        model = MembershipImage
        fields = ['image']


class MembershipCardSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    def get_images(self, obj):
        qs = MembershipImage.objects.filter(card=obj)
        return MembershipImageSerializer(qs, many=True, context=self.context).data

    class Meta:
        model = MembershipCard
        fields = ['title', 'amount', 'days', 'discount', 'customer_mobile', 'customer_mobile_s', 'images', 'is_open']


class MemberCardRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberCardRecord
        fields = ['order_no']


class MemberCardRecordCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=9, decimal_places=2, required=True)

    @atomic
    def create(self, validated_data):
        logger.error(validated_data)
        request = self.context.get('request')
        if not request.user.mobile:
            raise CustomAPIException('请先绑定手机')
        mc = MembershipCard.get()
        if mc.amount != validated_data['amount']:
            raise CustomAPIException('金额错误')
        pay_type = validated_data['pay_type']
        return MemberCardRecord.create_record(request.user, pay_type, mc)

    class Meta:
        model = MemberCardRecord
        fields = ['id', 'amount', 'receipt_id', 'pay_type']
        read_only_fields = ['receipt_id']


class AgreementRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgreementRecord
        fields = ['agree_member', 'agree_privacy', 'create_at', 'agree_agent']


class TheaterCardTicketLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TheaterCardTicketLevel
        fields = ['id', 'title', 'discount']


class TheaterCardCitySerializer(serializers.ModelSerializer):
    cities = DivisionSerializer(many=True)

    class Meta:
        model = TheaterCardCity
        fields = ['cities', 'discount']


class TheaterCardImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        from common.config import get_config
        config = get_config()
        return '{}{}'.format(config['template_url'], obj.image.url)

    class Meta:
        model = TheaterCardImage
        fields = ['image']


class TheaterCardSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    ticket_level = serializers.SerializerMethodField()
    cities = serializers.SerializerMethodField()

    def get_images(self, obj):
        qs = TheaterCardImage.objects.filter(card=obj)
        return TheaterCardImageSerializer(qs, many=True, context=self.context).data

    def get_ticket_level(self, obj):
        qs = TheaterCardTicketLevel.objects.filter(card=obj)
        return TheaterCardTicketLevelSerializer(qs, many=True, context=self.context).data

    def get_cities(self, obj):
        qs = TheaterCardCity.objects.filter(card=obj)
        return TheaterCardCitySerializer(qs, many=True, context=self.context).data

    class Meta:
        model = TheaterCard
        fields = ['title', 'amount', 'receive_amount', 'day_max_num', 'customer_mobile', 'customer_mobile_s', 'images',
                  'ticket_level', 'cities', 'is_open']


class TheaterCardOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TheaterCardOrder
        fields = ['order_no', 'card_no']


class TheaterCardOrderCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=9, decimal_places=2, required=True)
    pay_type = serializers.IntegerField(required=True)

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        if not request.user.mobile:
            raise CustomAPIException('请先绑定手机')
        from caches import get_redis, theater_card_order_create_key
        redis = get_redis()
        key = theater_card_order_create_key.format(request.user.id)
        if redis.setnx(key, 1):
            redis.expire(key, 5)
            card = TheaterCard.get_inst()
            if not card or not card.can_buy:
                raise CustomAPIException('会员卡暂不能购买')
            if card.amount != validated_data['amount']:
                raise CustomAPIException('金额错误')
            pay_type = validated_data['pay_type']
            return TheaterCardOrder.create_record(request.user, card, pay_type)
        else:
            raise CustomAPIException('请不要太快下单，稍后再试')

    class Meta:
        model = TheaterCardOrder
        fields = ['id', 'amount', 'receipt_id', 'pay_type']
        read_only_fields = ['receipt_id']


class TheaterCardUserRecordSerializer(serializers.ModelSerializer):
    today_buy = serializers.SerializerMethodField()

    def get_today_buy(self, obj):
        day_d = TheaterCardUserBuy.get_inst(obj)
        return day_d.num if day_d else 0

    class Meta:
        model = TheaterCardUserRecord
        fields = ['amount', 'card_no', 'discount_total', 'create_at', 'today_buy']


class TheaterCardUserDetailSerializer(serializers.ModelSerializer):
    card_data = serializers.SerializerMethodField()

    def get_card_data(self, obj):
        return dict(title=obj.card.title)

    class Meta:
        model = TheaterCardUserDetail
        fields = ['card_data', 'amount', 'create_at', 'charge_at']


class TheaterCardUserDetailOrderSerializer(serializers.ModelSerializer):
    card = TheaterCardSerializer()
    theater_card_amount = serializers.SerializerMethodField()

    def get_theater_card_amount(self, obj):
        return obj.amount

    class Meta:
        model = TheaterCardUserDetail
        fields = ['card', 'theater_card_amount', 'create_at', 'charge_at']


class TheaterCardChangeRecordSerializer(serializers.ModelSerializer):
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')
    order_data = serializers.SerializerMethodField()

    def get_order_data(self, obj):
        data = dict()
        if obj.ticket_order:
            order = obj.ticket_order
            data = dict(order_no=order.order_no, nickname=order.user.get_full_name(), session=str(order.session))
        return data

    class Meta:
        model = TheaterCardChangeRecord
        fields = ['amount', 'source_type', 'source_type_display', 'create_at', 'order_data']
