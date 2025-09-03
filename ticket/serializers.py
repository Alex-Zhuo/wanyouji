# -*- coding: utf-8 -*-

from rest_framework import serializers
from django.db.transaction import atomic
from mall.serializers import UserSerializer
from restframework_ext.exceptions import CustomAPIException
from shopping_points.serializers import DivisionSerializer
from ticket.models import Venues, Seat, TicketColor, ShowProject, ShowCollectRecord, SessionInfo, TicketFile, \
    SessionSeat, TicketOrder, TicketUserCode, ShowPerformer, PerformerFlag, PerformerFocusRecord, VenuesLogoImage, \
    ShowType, ShowsDetailImage, VenuesDetailImage, ShowUser, SessionChangeRecord, VenuesLayers, ShowComment, \
    ShowCommentImage, TicketBooking, TicketOrderChangePrice, ShowContentCategory, ShowPerformerBanner, TicketGiveRecord, \
    TicketGiveDetail, TicketOrderRealName, ShowContentCategorySecond, TicketWatchingNotice, TicketPurchaseNotice, \
    TicketOrderDiscount
import json
from mall.models import Receipt, UserAddress
from django.utils import timezone
import logging
from decimal import Decimal
from common.config import get_config
from django.db.models import Min
from common.utils import s_id_card

log = logging.getLogger(__name__)
USER_FLAG_AMOUNT = Decimal(0.01)


def get_origin(request):
    is_tiktok = False
    is_ks = False
    is_xhs = False
    if request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok':
        is_tiktok = True
    elif request.META.get('HTTP_AUTH_ORIGIN') == 'ks':
        is_ks = True
    elif request.META.get('HTTP_AUTH_ORIGIN') == 'xhs':
        is_xhs = True
    return is_tiktok, is_ks, is_xhs


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = '__all__'


class VenuesLogoImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url)

    class Meta:
        model = VenuesLogoImage
        fields = '__all__'


class VenuesDetailImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url)

    class Meta:
        model = VenuesDetailImage
        fields = '__all__'


class PKtoNoSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    def get_id(self, obj):
        return obj.no

    class Meta:
        fields = ['id', 'no']


class VenuesCustomerDetailSerializer(PKtoNoSerializer):
    city = DivisionSerializer()
    logo_images = serializers.SerializerMethodField()
    detail_images = serializers.SerializerMethodField()

    def get_logo_images(self, obj):
        qs = VenuesLogoImage.objects.filter(venue=obj)
        return VenuesLogoImageSerializer(qs, many=True, context=self.context).data

    def get_detail_images(self, obj):
        qs = VenuesDetailImage.objects.filter(venue=obj)
        return VenuesDetailImageSerializer(qs, many=True, context=self.context).data

    class Meta:
        model = Venues
        fields = PKtoNoSerializer.Meta.fields + ['name', 'layers', 'city', 'lat', 'lng', 'address', 'desc',
                                                 'map', 'custom_mobile', 'custom_wechat', 'custom_code', 'logo_images',
                                                 'detail_images']


class VenuesDetailSerializer(VenuesCustomerDetailSerializer):
    class Meta:
        model = Venues
        fields = VenuesCustomerDetailSerializer.Meta.fields + ['is_use', 'is_seat', 'seat_data', 'direction']


class VenuesLayersSerializer(serializers.ModelSerializer):
    class Meta:
        model = VenuesLayers
        fields = '__all__'


class VenuesNewSerializer(PKtoNoSerializer):
    city = DivisionSerializer()

    class Meta:
        model = Venues
        fields = PKtoNoSerializer.Meta.fields + ['name', 'city']


class VenuesAiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venues
        fields = ['name', 'lat', 'lng', 'address']


class VenuesSerializer(VenuesNewSerializer):
    logo = serializers.SerializerMethodField()
    map = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    layers_data = serializers.SerializerMethodField()
    custom_code = serializers.SerializerMethodField()

    def get_layers_data(self, obj):
        layers = VenuesLayers.objects.filter(venue=obj)
        return VenuesLayersSerializer(layers, many=True).data

    def get_price(self, obj):
        sp = ShowProject.objects.filter(venues_id=obj.id, status=ShowProject.STATUS_ON).order_by('price').first()
        return sp.price if sp else 0

    def get_logo(self, obj):
        config = get_config()
        domain = config.get('template_url')
        inst = VenuesLogoImage.objects.filter(venue=obj).first()
        return '{}/{}'.format(domain, inst.image.url) if inst else None

    def get_map(self, obj):
        config = get_config()
        domain = config.get('template_url')
        return '{}/{}'.format(domain, obj.map.url) if obj.map else None

    def get_custom_code(self, obj):
        config = get_config()
        domain = config.get('template_url')
        return '{}/{}'.format(domain, obj.custom_code.url) if obj.custom_code else None

    class Meta:
        model = Venues
        fields = VenuesNewSerializer.Meta.fields + ['address', 'logo', 'custom_mobile', 'custom_wechat', 'custom_code',
                                                    'layers',
                                                    'map', 'price', 'layers_data', 'lat', 'lng']


class VenuesOrderSerializer(PKtoNoSerializer):
    custom_code = serializers.SerializerMethodField()

    def get_custom_code(self, obj):
        config = get_config()
        domain = config.get('template_url')
        return '{}/{}'.format(domain, obj.custom_code.url) if obj.custom_code else None

    class Meta:
        model = Venues
        fields = PKtoNoSerializer.Meta.fields + ['name', 'address', 'custom_mobile', 'custom_wechat',
                                                 'custom_code', 'lat', 'lng']


class SeatCreateSerializer(serializers.ModelSerializer):
    venue_id = serializers.CharField(required=True)
    seat = serializers.ListField(required=True)

    def validate_venue_id(self, value):
        try:
            inst = Venues.objects.get(no=value)
            # if inst.is_seat:
            #     raise CustomAPIException('已经编辑过座位了')
            return inst
        except Venues.DoesNotExist:
            raise CustomAPIException('找不到场馆')

    @atomic
    def create(self, validated_data):
        venue = validated_data.get('venue_id')
        layer_list = validated_data.get('seat')
        if SessionInfo.objects.filter(show__venues=venue, is_price=True, is_delete=False):
            raise CustomAPIException('该场馆已被场次应用，不能修改')
        record = []
        if venue.is_seat:
            Seat.objects.filter(venue=venue).delete()
        for lay in layer_list:
            layers = lay['layers']
            for seat in lay['data']:
                seat_no = '{}_{}_{}_{}'.format(venue.id, layers, seat['y'], seat['x'])
                record.append(Seat(venue=venue, row=seat['y'], column=seat['x'], layers=layers, seat_no=seat_no))
                seat['seat_no'] = seat_no
        Seat.objects.bulk_create(record)
        venue.seat_data = json.dumps(layer_list)
        venue.is_seat = True
        venue.save(update_fields=['seat_data', 'is_seat'])

    class Meta:
        model = Seat
        fields = ['venue_id', 'seat']


class TicketColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketColor
        fields = '__all__'


class TicketFileSerializer(serializers.ModelSerializer):
    color = TicketColorSerializer()

    class Meta:
        model = TicketFile
        fields = ['id', 'title', 'color', 'origin_price', 'price', 'stock', 'sales', 'desc', 'is_tiktok', 'is_ks',
                  'is_xhs', 'push_xhs', 'status']


class TicketColorBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketColor
        fields = ['name', 'code']


class TicketFileCacheSerializer(serializers.ModelSerializer):
    color = serializers.SerializerMethodField()

    def get_color(self, obj):
        if obj.color:
            data = TicketColorBaseSerializer(obj.color, context=self.context).data
        else:
            data = dict(name=None, code=obj.color_code)
        return data

    class Meta:
        model = TicketFile
        fields = ['id', 'title', 'color', 'origin_price', 'price', 'stock', 'desc']


class TicketFileBackSerializer(serializers.ModelSerializer):
    color = TicketColorSerializer()

    class Meta:
        model = TicketFile
        fields = ['id', 'color', 'price']


class TicketFileCreateSerializer(serializers.ModelSerializer):
    session_id = serializers.CharField(required=True)
    record = serializers.ListField(required=True)

    def create(self, validated_data):
        record = validated_data.get('record')
        # qs_list = []
        session = None
        for r in record:
            r['session_id'] = validated_data.get('session_id')
            if not session:
                session = SessionInfo.objects.filter(no=r['session_id']).first()
            if not session:
                raise CustomAPIException('场次错误')
            r['title'] = session.show.title
            if not r.get('stock'):
                r['stock'] = 0
            inst = TicketFile.objects.create(session_id=session.id, title=session.show.title, color_id=r['color_id'],
                                             origin_price=r['origin_price'], price=r['price'], total_stock=r['stock'],
                                             stock=r['stock'], desc=r['desc'], is_tiktok=r['is_tiktok'],
                                             is_ks=r.get('is_ks', False),
                                             status=r['status'], is_xhs=r.get('is_xhs', False))
            if inst.status:
                inst.redis_stock()
            inst.redis_ticket_level_cache()
        # TicketFile.objects.bulk_create(qs_list)

    class Meta:
        model = TicketFile
        fields = ['record', 'session_id']


class TicketFileChangeSerializer(serializers.ModelSerializer):
    record = serializers.ListField(required=True)

    @atomic
    def create(self, validated_data):
        record = validated_data.get('record')
        qs_list = []
        qs_list_create = []
        session = None
        for r in record:
            t_id = r.get('id')
            status = r.get('status')
            is_change = False
            if t_id:
                inst = TicketFile.objects.filter(id=int(t_id)).first()
                session = inst.session
                # if session.status == session.STATUS_ON:
                #     raise CustomAPIException('请先下架场次再修改票档')
                if inst.status != status or inst.desc != r['desc'] or inst.is_tiktok != r[
                    'is_tiktok'] or inst.is_ks != r['is_ks']:
                    is_change = True
                inst.status = status
                inst.desc = r['desc']
                stock = int(r['stock'])
                change_stock = inst.stock != stock
                inst.total_stock = stock
                inst.stock = stock
                inst.is_tiktok = r['is_tiktok']
                inst.is_ks = r.get('is_ks', False)
                inst.is_xhs = r.get('is_xhs', False)
                if inst.stock < 0:
                    raise CustomAPIException('修改后库存不能小于0')
                if inst.product_id and inst.is_tiktok and change_stock and inst.push_status == inst.PUSH_SUCCESS:
                    try:
                        from douyin import get_dou_yin
                        dy = get_dou_yin()
                        ret = dy.product_free_audit(inst.product_id, stock_qty=inst.stock, change_stock=True)
                    except Exception as e:
                        raise CustomAPIException(e)
                    if ret['error_code'] != 0:
                        log.error('更改库存失败,{}'.format(ret['description']))
                # qs_list.append(inst)
                inst.save(update_fields=['desc', 'stock', 'status', 'total_stock', 'is_tiktok', 'is_ks', 'is_xhs'])
                if change_stock:
                    msg = '修改库存为，{}'.format(stock)
                    inst.set_log(self.context.get('request'), msg)
            else:
                if not session:
                    session = SessionInfo.objects.filter(id=r['session_id']).first()
                if not session:
                    raise CustomAPIException('场次错误')
                if not r.get('stock'):
                    r['stock'] = 0
                inst = TicketFile.objects.create(session_id=session.id, title=session.show.title,
                                                 color_id=r['color_id'],
                                                 origin_price=r['origin_price'], price=r['price'],
                                                 total_stock=r['stock'], is_ks=r['is_ks'],
                                                 stock=r['stock'], desc=r['desc'], is_tiktok=r['is_tiktok'],
                                                 status=r['status'], is_xhs=r.get('is_xhs', False))
                is_change = True
                change_stock = True
            if is_change:
                inst.redis_ticket_level_cache()
            if change_stock:
                inst.redis_stock()
        # if qs_list:
        #     TicketFile.objects.bulk_update(qs_list, ['desc', 'stock', 'status', 'total_stock', 'is_tiktok'])
        # if qs_list_create:
        #     TicketFile.objects.bulk_create(qs_list_create)

    class Meta:
        model = TicketFile
        fields = ['record']


class SessionCopySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)
    start_at = serializers.TimeField(required=True)
    end_at = serializers.TimeField(required=True)
    level_dict = serializers.CharField(required=True)
    date_at_list = serializers.CharField(required=True)

    def validate_id(self, value):
        try:
            inst = SessionInfo.objects.get(pk=value)
            return inst
        except SessionInfo.DoesNotExist:
            raise CustomAPIException('找不到场次')

    def create(self, validated_data):
        # json  dict(1=10,2=20)
        from caches import get_pika_redis, pika_copy_goods
        redis = get_pika_redis()
        from common.utils import common_return
        ret = common_return()
        if redis.setnx(pika_copy_goods, 1):
            redis.expire(pika_copy_goods, 3)
            from datetime import datetime
            session = validated_data.pop('id')
            start_at = validated_data['start_at']
            end_at = validated_data['end_at']
            date_at_list = json.loads(validated_data['date_at_list'])
            level_dict = json.loads(validated_data['level_dict'])
            # log.warning(date_at_list)
            for date_at in date_at_list:
                dd = datetime.strptime(date_at, "%Y-%m-%d").date()
                start = datetime.combine(dd, start_at)
                end = datetime.combine(dd, end_at)
                status, msg, new_session = session.layer_session(level_dict)
                # log.warning(status)
                if status:
                    log.warning(start)
                    log.warning(end)
                    new_session.update_start_at_and_end_at(start, end)
                else:
                    log.error(msg)
                    ret['code'] = 400
                    ret['msg'] = msg
                    continue
        else:
            raise CustomAPIException('请勿操作太快')
        return ret

    class Meta:
        model = SessionInfo
        fields = ['id', 'start_at', 'end_at', 'level_dict', 'date_at_list']


class SessionInfoSerializer(PKtoNoSerializer):
    can_buy = serializers.SerializerMethodField()
    change = serializers.SerializerMethodField()

    def get_change(self, obj):
        sc = SessionChangeRecord.objects.filter(session=obj).first()
        return dict(old_end_at=sc.old_end_at, new_end_at=sc.new_end_at,
                    create_at=sc.create_at.strftime('%Y-%m-%dT%H:%M:%S')) if sc else None

    def get_can_buy(self, obj):
        return obj.can_buy

    class Meta:
        model = SessionInfo
        fields = PKtoNoSerializer.Meta.fields + ['show', 'start_at', 'end_at', 'tiktok_store', 'valid_start_time',
                                                 'desc', 'order_limit_num', 'is_real_name_buy', 'is_name_buy',
                                                 'one_id_one_ticket',
                                                 'status', 'create_at', 'is_price', 'push_status', 'can_buy', 'change',
                                                 'is_sale_off', 'is_dy_code',
                                                 'dc_expires_in']


# 后台搜索框不需要no
class SessionSearchListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return str(obj)

    def get_title(self, obj):
        return str(obj.show)

    class Meta:
        model = SessionInfo
        fields = ['id', 'title', 'start_at', 'name']


class SessionExpressFeeSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=True)
    express_address_id = serializers.IntegerField(label='收货地址', write_only=True)

    def validate_express_address_id(self, value):
        user = self.context['request'].user
        try:
            return UserAddress.objects.get(user=user, pk=value)
        except UserAddress.DoesNotExist:
            raise CustomAPIException('收获地址找不到')

    def validate_session_id(self, value):
        try:
            return SessionInfo.objects.get(is_paper=True, no=value)
        except SessionInfo.DoesNotExist:
            raise CustomAPIException('该场次不需要邮费')

    def create(self, validated_data):
        addr = validated_data['express_address_id']
        session = validated_data['session_id']
        division = addr.division
        ret = dict(express_disabled=True, remark=None, fee=0)
        template = session.express_template
        if template:
            st = session.check_express_fee_date()
            if st:
                ret['express_disabled'] = False
            else:
                if template.is_excluded(division):
                    ret['remark'] = '不支持发货到%s' % str(division)
                else:
                    ret['express_disabled'] = False
                    ret['fee'] = template.get_fee(division, 1)
        else:
            ret['remark'] = '未设置模板'
        return ret

    class Meta:
        model = SessionInfo
        fields = ['session_id', 'express_address_id']


class ShowTypeBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowType
        fields = ['name', 'slug']


class ShowTypeSerializer(ShowTypeBasicSerializer):
    source_type_display = serializers.ReadOnlyField(source='get_source_type_display')

    class Meta:
        model = ShowType
        fields = ShowTypeBasicSerializer.Meta.fields + ['source_type', 'source_type_display']


class ShowContentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowContentCategory
        fields = ['title', 'en_title']


class ShowContentCategorySecondSerializer(serializers.ModelSerializer):
    show_type = ShowTypeBasicSerializer()
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        return str(obj)

    class Meta:
        model = ShowContentCategorySecond
        fields = ['id', 'show_type', 'title']


class ShowProjectCommonRelateSerializer(PKtoNoSerializer):
    cate = serializers.SerializerMethodField()
    show_type = serializers.SerializerMethodField()

    def get_show_type(self, obj):
        from caches import get_pika_redis, redis_show_type_copy_key
        with get_pika_redis() as pika:
            data = pika.hget(redis_show_type_copy_key, str(obj.show_type_id))
        # data = None
        if not data:
            return ShowTypeSerializer(obj.show_type, context=self.context).data
        else:
            return json.loads(data)

    def get_cate(self, obj):
        data = None
        if obj.cate:
            from caches import get_pika_redis, redis_show_content_copy_key
            with get_pika_redis() as pika:
                data = pika.hget(redis_show_content_copy_key, str(obj.cate_id))
        # data = None
        if data:
            return json.loads(data)
        else:
            return ShowContentCategorySerializer(obj.cate).data


class ShowProjectRecommendSerializer(ShowProjectCommonRelateSerializer):
    date = serializers.SerializerMethodField()
    flag = serializers.SerializerMethodField()
    venue = serializers.SerializerMethodField()

    def get_venue(self, obj):
        from caches import get_pika_redis, redis_venues_copy_key
        with get_pika_redis() as pika:
            data = pika.hget(redis_venues_copy_key, str(obj.venues_id))
        # data = None
        if data:
            data = json.loads(data)
            data['city'] = data['city'].get('city')
            return data
        else:
            return VenuesNewSerializer(obj.venues, context=self.context).data

    def get_flag(self, obj):
        inst = obj.flag.first()
        return inst.title if inst else None

    def get_date(self, obj):
        inst = SessionInfo.objects.filter(show=obj).first()
        return dict(start_at=inst.start_at.strftime("%m月%d日 %H:%M"),
                    end_at=inst.end_at.strftime("%m月%d日 %H:%M")) if inst else None

    class Meta:
        model = ShowProject
        fields = ['id', 'no', 'title', 'logo_mobile', 'date', 'price', 'venue', 'flag', 'cate', 'show_type']


class ShowProjectSerializer(ShowProjectCommonRelateSerializer):
    date = serializers.SerializerMethodField()
    venues = serializers.SerializerMethodField()

    def get_venues(self, obj):
        from caches import get_pika_redis, redis_venues_copy_key
        with get_pika_redis() as pika:
            data = pika.hget(redis_venues_copy_key, str(obj.venues_id))
        # data = None
        if data:
            return json.loads(data)
        else:
            return VenuesNewSerializer(obj.venues, context=self.context).data

    def get_date(self, obj):
        from caches import get_pika_redis, redis_show_date_copy
        with get_pika_redis() as pika:
            date_data = pika.hget(redis_show_date_copy, obj.id)
        # date_data = None
        if date_data:
            return json.loads(date_data)
        else:
            inst = SessionInfo.objects.filter(show_id=obj.id, status=SessionInfo.STATUS_ON, is_delete=False).order_by(
                'start_at').first()
            create_at = obj.create_at.strftime("%Y-%m-%dT%H:%M:%S")
            return dict(start_at=inst.start_at, end_at=inst.end_at) if inst else dict(start_at=create_at,
                                                                                      end_at=create_at)

    class Meta:
        model = ShowProject
        fields = ['id', 'no', 'title', 'logo_mobile', 'date', 'price', 'venues', 'cate', 'show_type']


class ShowStaffSerializer(PKtoNoSerializer):
    show_type = ShowTypeSerializer()
    venues = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    def get_date(self, obj):
        inst = SessionInfo.objects.filter(show=obj, end_at__gt=timezone.now()).order_by('start_at').first()
        create_at = obj.create_at.strftime("%Y-%m-%dT%H:%M:%S")
        return dict(start_at=inst.start_at.strftime("%Y-%m-%dT%H:%M:%S"),
                    end_at=inst.end_at.strftime("%Y-%m-%dT%H:%M:%S")) if inst else dict(
            start_at=create_at,
            end_at=create_at)

    def get_venues(self, obj):
        return VenuesSerializer(obj.venues, context=self.context).data

    class Meta:
        model = ShowProject
        fields = '__all__'


class SessionSeatBackSerializer(serializers.ModelSerializer):
    seat_no = serializers.SerializerMethodField()
    can_buy = serializers.SerializerMethodField()

    def get_can_buy(self, obj):
        return obj.can_buy()

    def get_seat_no(self, obj):
        return obj.seats.seat_no

    class Meta:
        model = SessionSeat
        fields = '__all__'


class SessionInfoEditDetailSerializer(PKtoNoSerializer):
    ticket_level = serializers.SerializerMethodField()
    show = serializers.SerializerMethodField()

    def get_ticket_level(self, obj):
        request = self.context.get('request')
        qs = TicketFile.objects.filter(session_id=obj.id)
        if request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok':
            qs = qs.filter(push_status=TicketFile.PUSH_SUCCESS, is_tiktok=True, product_id__isnull=False)
        return TicketFileSerializer(qs, many=True, context=self.context).data

    def get_show(self, obj):
        return ShowProjectSerializer(obj.show, context=self.context).data

    class Meta:
        model = SessionInfo
        fields = [f.name for f in SessionInfo._meta.fields] + ['ticket_level']


class SessionInfoDetailSerializer(SessionInfoEditDetailSerializer):
    seats = serializers.SerializerMethodField()

    def get_seats(self, obj):
        ss_list = SessionSeat.objects.filter(session_id=obj.id)
        data = SessionSeatBackSerializer(ss_list, many=True).data
        return data

    class Meta:
        model = SessionInfo
        fields = SessionInfoEditDetailSerializer.Meta.fields + ['seats']


class ShowsDetailImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowsDetailImage
        fields = '__all__'


class ShowSessionCacheSerializer(PKtoNoSerializer):
    express_end_at = serializers.SerializerMethodField()

    def get_express_end_at(self, obj):
        return obj.express_end_at

    class Meta:
        model = SessionInfo
        fields = PKtoNoSerializer.Meta.fields + ['start_at', 'end_at', 'valid_start_time', 'desc', 'order_limit_num',
                                                 'status', 'create_at', 'is_price', 'push_status', 'has_seat',
                                                 'is_sale_off', 'one_id_one_ticket',
                                                 'is_theater_discount', 'is_paper', 'express_end_at', 'is_name_buy',
                                                 'name_buy_num', 'source_type', 'cy_discount_overlay']


class ShowSessionInfoSerializer(PKtoNoSerializer):
    ticket_level = serializers.SerializerMethodField()

    def get_ticket_level(self, obj):
        request = self.context.get('request')
        qs = TicketFile.objects.filter(session=obj, status=True)
        # if obj.has_seat == SessionInfo.SEAT_NO:
        #     qs = qs.filter(stock__gt=0)
        if request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok':
            qs = qs.filter(push_status=TicketFile.PUSH_SUCCESS, is_tiktok=True, product_id__isnull=False)
        return TicketFileSerializer(qs, many=True, context=self.context).data

    class Meta:
        model = SessionInfo
        fields = PKtoNoSerializer.Meta.fields + ['show', 'start_at', 'end_at', 'tiktok_store', 'valid_start_time',
                                                 'desc', 'order_limit_num',
                                                 'status', 'create_at', 'is_price', 'push_status', 'ticket_level',
                                                 'has_seat', 'is_sale_off',
                                                 'is_theater_discount']


# 测试场次才使用这里
class ShowProjectDetailSerializer(ShowProjectSerializer):
    sessions = serializers.SerializerMethodField()
    can_buy = serializers.SerializerMethodField()
    is_collect = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    sale_time_timestamp = serializers.SerializerMethodField()

    def get_sale_time_timestamp(self, obj):
        from common.utils import get_timestamp
        return get_timestamp(obj.sale_time) if obj.sale_time else None

    def get_images(self, obj):
        qs = ShowsDetailImage.objects.filter(show=obj)
        return ShowsDetailImageSerializer(qs, many=True, context=self.context).data

    def get_is_collect(self, obj):
        user = self.context.get('request').user
        inst = ShowCollectRecord.objects.filter(show=obj, user=user).first()
        return inst.is_collect if inst else False

    def get_can_buy(self, obj):
        if obj.is_test:
            from common.utils import check_tiktok_version
            request = self.context.get('request')
            # log.debug(request.META)
            ret = check_tiktok_version(request)
            log.debug(request.META.get('HTTP_VERSION'))
            return ret
        return obj.can_buy

    def get_sessions(self, obj):
        request = self.context.get('request')
        qs = SessionInfo.objects.filter(show=obj, status=SessionInfo.STATUS_ON, is_delete=False)
        if request.META.get('HTTP_AUTH_ORIGIN') == 'tiktok':
            qs = qs.filter(dy_status=SessionInfo.STATUS_ON)
        qs = qs.order_by('start_at')
        return ShowSessionInfoSerializer(qs, many=True, context=self.context).data

    class Meta:
        model = ShowProject
        fields = ['id', 'no', 'title', 'lat', 'lng', 'content', 'notice', 'display_order', 'is_test', 'status', 'cate',
                  'venues', 'show_type', 'is_recommend', 'dy_show_date', 'price', 'sale_time', 'session_end_at',
                  'origin_amount', 'logo_mobile', 'date', 'sessions', 'can_buy', 'is_collect', 'images',
                  'sale_time_timestamp', 'source_type']


class SessionInfoStaffSerializer(PKtoNoSerializer):
    sum_data = serializers.SerializerMethodField()

    def get_sum_data(self, obj):
        ss = list(SessionInfo.objects.filter(main_session_id=obj.id).values_list('id', flat=True) or [])
        if len(ss) > 0:
            ss.append(obj.id)
            qs = TicketUserCode.objects.filter(session_id__in=ss)
        else:
            qs = TicketUserCode.objects.filter(session_id=obj.id)
        qs = qs.exclude(status=TicketUserCode.STATUS_CANCEL)
        finish = qs.filter(status=TicketUserCode.STATUS_CHECK).count()
        uncheck = qs.filter(status=TicketUserCode.STATUS_DEFAULT).count()
        over_time_num = qs.filter(status=TicketUserCode.STATUS_OVER_TIME).count()
        total = qs.count()
        return dict(finish=finish, uncheck=uncheck, over_time_num=over_time_num, total=total)

    class Meta:
        model = SessionInfo
        fields = PKtoNoSerializer.Meta.fields + ['sum_data', 'start_at', 'end_at']


class SessionInfoStaffDetailSerializer(PKtoNoSerializer):
    sum_data = serializers.SerializerMethodField()

    def get_sum_data(self, obj):
        qs = TicketUserCode.objects.filter(session_id=obj.id).exclude(status=TicketUserCode.STATUS_CANCEL)
        finish = qs.filter(status=TicketUserCode.STATUS_CHECK).count()
        uncheck = qs.filter(status=TicketUserCode.STATUS_DEFAULT).count()
        over_time_num = qs.filter(status=TicketUserCode.STATUS_OVER_TIME).count()
        total = qs.count()
        items = []
        tf_qs = TicketFile.objects.filter(session_id=obj.id).order_by('origin_price')
        for tf in tf_qs:
            l_qs = qs.filter(level_id=tf.id)
            l_finish = l_qs.filter(status=TicketUserCode.STATUS_CHECK).count()
            l_uncheck = l_qs.filter(status=TicketUserCode.STATUS_DEFAULT).count()
            l_over_time_num = l_qs.filter(status=TicketUserCode.STATUS_OVER_TIME).count()
            items.append(
                dict(origin_price=tf.origin_price, price=tf.price, finish=l_finish, uncheck=l_uncheck,
                     over_time_num=l_over_time_num,
                     total=l_qs.count()))
        return dict(finish=finish, uncheck=uncheck, actual_amount=obj.actual_amount, over_time_num=over_time_num,
                    total=total, items=items)

    class Meta:
        model = SessionInfo
        fields = PKtoNoSerializer.Meta.fields + ['sum_data', 'start_at', 'end_at']


# class ShowProjectStaffSerializer(ShowStaffSerializer):
#     sessions = serializers.SerializerMethodField()
#
#     def get_sessions(self, obj):
#         qs = SessionInfo.objects.filter(show=obj, status=SessionInfo.STATUS_ON, end_at__gt=timezone.now(),
#                                         is_delete=False)
#         return SessionInfoStaffSerializer(qs, many=True, context=self.context).data
#
#     class Meta:
#         model = ShowProject
#         fields = '__all__'


class ShowProjectStaffNewSerializer(ShowStaffSerializer):
    sessions = serializers.SerializerMethodField()

    def get_sessions(self, obj):
        qs = SessionInfo.objects.filter(show=obj, end_at__gt=timezone.now(), is_delete=False,
                                        main_session__isnull=True).order_by('start_at')
        return SessionInfoStaffSerializer(qs, many=True, context=self.context).data

    class Meta:
        model = ShowProject
        fields = '__all__'


class ShowProjectStatisticsSerializer(ShowStaffSerializer):
    sessions = serializers.SerializerMethodField()

    def get_sessions(self, obj):
        status = self.context.get('request').GET.get('status')
        qs = SessionInfo.objects.filter(show=obj, is_delete=False)
        if status:
            status = int(status)
            if status == 1:
                qs = qs.filter(end_at__gt=timezone.now())
            else:
                qs = qs.filter(end_at__lte=timezone.now())
        ids = list(qs.values_list('id', flat=True))
        tu_qs = TicketUserCode.objects.filter(session_id__in=ids).exclude(status=TicketUserCode.STATUS_CANCEL)
        check_num = tu_qs.filter(status=TicketUserCode.STATUS_CHECK).count()
        buy_num = tu_qs.count()
        return dict(num=len(ids), check_num=check_num, buy_num=buy_num)

    class Meta:
        model = ShowProject
        fields = '__all__'


class ShowCollectRecordSerializer(serializers.ModelSerializer):
    show = ShowProjectRecommendSerializer()

    class Meta:
        model = ShowCollectRecord
        fields = ['is_collect', 'show', 'create_at']


class ShowPerformerRecommendSerializer(serializers.ModelSerializer):
    show_num = serializers.SerializerMethodField()

    def get_show_num(self, obj):
        return obj.show_num

    class Meta:
        model = ShowPerformer
        fields = '__all__'


class ShowPerformerSerializer(ShowPerformerRecommendSerializer):
    is_focus = serializers.SerializerMethodField()

    def get_is_focus(self, obj):
        user = self.context.get('request').user
        inst = PerformerFocusRecord.objects.filter(user=user, performer=obj).first()
        return inst.is_collect if inst else False

    class Meta:
        model = ShowPerformer
        fields = '__all__'


class PerformerFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformerFlag
        fields = '__all__'


class ShowPerformerBannerSerializer(serializers.ModelSerializer):
    img = serializers.SerializerMethodField()

    def get_img(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.img.url)

    class Meta:
        model = ShowPerformerBanner
        fields = ['id', 'img']


class ShowPerformerDetailSerializer(ShowPerformerSerializer):
    shows = serializers.SerializerMethodField()
    flag = PerformerFlagSerializer(many=True)
    banners = serializers.SerializerMethodField()

    def get_banners(self, obj):
        qs = ShowPerformerBanner.objects.filter(performer=obj, is_show=True)
        return ShowPerformerBannerSerializer(qs, many=True, context=self.context).data

    def get_shows(self, obj):
        queryset = ShowProject.objects.filter(status=ShowProject.STATUS_ON, performer=obj,
                                              session_info__status=SessionInfo.STATUS_ON)
        queryset = queryset.annotate(sa=Min("session_info__start_at"))
        queryset = queryset.order_by('-display_order', 'sa')
        return ShowProjectSerializer(queryset, many=True, context=self.context).data

    class Meta:
        model = ShowPerformer
        fields = '__all__'


class SessionSeatSerializer(serializers.ModelSerializer):
    # ticket_level = TicketFileSerializer()
    # seats = SeatSerializer()
    can_buy = serializers.SerializerMethodField()

    def get_can_buy(self, obj):
        return obj.can_buy()

    class Meta:
        model = SessionSeat
        fields = ['row', 'column', 'layers', 'price', 'showRow', 'showCol', 'box_no_special', 'order_no', 'can_buy']


class SessionSeatCreateSerializer(serializers.ModelSerializer):
    record = serializers.ListField(required=True)
    cacheSeat = serializers.CharField(required=True)

    @atomic
    def create(self, validated_data):
        # 后面要改成celery
        log.debug('设置座位1')
        # try:
        request = self.context.get('request')
        SessionSeat.create_record(validated_data['record'], cache_seat=validated_data['cacheSeat'], request=request)
        # except Exception as e:
        #     log.debug(e)
        #     raise CustomAPIException('重复设置座位')
        log.debug('设置座位2')
        return

    class Meta:
        model = SessionSeat
        fields = ['record', 'cacheSeat']


class TicketUserCodeSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    session_seat = SessionSeatSerializer()
    check_user = serializers.SerializerMethodField()
    # code_img = serializers.SerializerMethodField()
    snapshot = serializers.SerializerMethodField()
    give_status_display = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, obj):
        return obj.code

    # give_status = serializers.SerializerMethodField()
    #
    # def get_give_status(self, obj):
    #     if obj.status == TicketUserCode.STATUS_DEFAULT:
    #         return obj.give_status
    #     else:
    #         return -1

    def get_give_status_display(self, obj):
        if obj.status == TicketUserCode.STATUS_DEFAULT:
            return obj.get_give_status_display()
        else:
            return '已使用'

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.snapshot)
        return snapshot

    def get_check_user(self, obj):
        return dict(name=str(obj.check_user) if obj.check_user else None)

    # def get_code_img(self, obj):
    #     url, code = obj.get_code_img_new()
    #     request = self.context.get('request')
    #     return request.build_absolute_uri(obj.code_img.url)

    class Meta:
        model = TicketUserCode
        fields = ['id', 'session_seat', 'status', 'status_display', 'check_user', 'code', 'check_at',
                  'snapshot', 'give_status', 'give_status_display', 'give_mobile']


class TicketUserCodeNewSerializer(TicketUserCodeSerializer):
    code_img_data = serializers.SerializerMethodField()

    def get_code_img_data(self, obj):
        request = self.context.get('request')
        refresh = request.GET.get('refresh')
        code = None
        can_share = False
        deadline_at = None
        deadline_timestamp = None
        if obj.status == TicketUserCode.STATUS_DEFAULT:
            is_refresh = True if refresh else False
            url, code = obj.get_code_img_new(is_refresh)
            can_share, deadline_at, deadline_timestamp = obj.check_can_share()
        else:
            url = obj.code_img.url if obj.code_img else None
        return dict(url=request.build_absolute_uri(url) if url else None, code=code, can_share=can_share,
                    deadline_at=deadline_at, deadline_timestamp=deadline_timestamp)

    class Meta:
        model = TicketUserCode
        fields = TicketUserCodeSerializer.Meta.fields + ['code_img_data']


class TicketOrderRealNameSerializer(serializers.ModelSerializer):
    id_card = serializers.SerializerMethodField()

    def get_id_card(self, obj):
        return s_id_card(obj.id_card) if obj.id_card else None

    class Meta:
        model = TicketOrderRealName
        fields = ['name', 'mobile', 'id_card']


class TicketOrderDiscountSerializer(serializers.ModelSerializer):
    discount_type_display = serializers.ReadOnlyField(source='get_discount_type_display')

    class Meta:
        model = TicketOrderDiscount
        fields = ['discount_type_display', 'title', 'amount']


class TicketOrderSerializer(serializers.ModelSerializer):
    snapshot = serializers.SerializerMethodField()
    status_display = serializers.ReadOnlyField(source='get_status_display')
    session = SessionInfoSerializer()
    venue = VenuesOrderSerializer()
    user = serializers.SerializerMethodField()
    pay_end_at = serializers.SerializerMethodField()
    can_margin = serializers.SerializerMethodField()
    create_at = serializers.SerializerMethodField()
    can_comment = serializers.SerializerMethodField()
    show_express_address = serializers.SerializerMethodField()
    express_status_display = serializers.ReadOnlyField(source='get_express_status_display')
    id = serializers.SerializerMethodField()
    receipt = serializers.SerializerMethodField()
    channel_type_display = serializers.ReadOnlyField(source='get_channel_type_display')

    def get_id(self, obj):
        return obj.order_no

    def get_receipt(self, obj):
        return obj.receipt.payno if obj.receipt else None

    def get_show_express_address(self, obj):
        return obj.show_express_address

    def get_can_comment(self, obj):
        return not obj.is_comment and not obj.session.close_comment

    def get_create_at(self, obj):
        return obj.create_at.strftime('%Y-%m-%dT%H:%M:%S')

    def get_can_margin(self, obj):
        # 状态为待核销或者已付款，且未结束
        st = obj.channel_type == TicketOrder.SR_DEFAULT and obj.status in [TicketOrder.STATUS_FINISH,
                                                                           TicketOrder.STATUS_PAID]
        # return obj.session.show.show_type != ShowType.xunyan() and st and timezone.now() < obj.session.end_at
        return st and timezone.now() < obj.session.end_at

    def get_pay_end_at(self, obj):
        return obj.get_end_at()

    def get_user(self, obj):
        user = obj.user
        if user:
            return dict(nickname=user.get_full_name(), name=user.mobile)
        else:
            return dict(nickname='', name='')

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.snapshot)
        logo = snapshot.get('logo')
        if logo and 'http' not in logo:
            config = get_config()
            snapshot['logo'] = '{}/{}'.format(config['template_url'], logo)
        log.error(snapshot)
        sc = SessionChangeRecord.objects.filter(session=obj.session).first()
        if sc:
            snapshot['start_at'] = sc.new_start_at.strftime('%Y-%m-%d %H:%M')
            snapshot['end_at'] = sc.new_end_at.strftime('%Y-%m-%d %H:%M')
        return snapshot

    class Meta:
        model = TicketOrder
        fields = ['id', 'title', 'mobile', 'express_address', 'order_no', 'tiktok_order_id', 'ks_order_no',
                  'multiply', 'amount', 'actual_amount', 'discount_amount', 'express_fee', 'card_jc_amount',
                  'refund_amount', 'order_type', 'status', 'express_status', 'is_cancel_pay',
                  'receipt', 'pay_type', 'pay_at', 'deliver_at', 'create_at', 'start_at', 'end_at',
                  'is_paper', 'express_no', 'express_name', 'express_comp_no', 'snapshot',
                  'status_display', 'session', 'venue', 'user', 'pay_end_at', 'can_margin',
                  'can_comment', 'show_express_address', 'express_status_display', 'channel_type',
                  'channel_type_display']


class TicketOrderDetailSerializer(TicketOrderSerializer):
    session = SessionInfoSerializer()
    code_list = serializers.SerializerMethodField()
    snapshot = serializers.SerializerMethodField()
    show_data = serializers.SerializerMethodField()

    def get_show_data(self, obj):
        data = dict(content=None, notice=None)
        if obj.session and obj.session.show:
            show = obj.session.show
            data['content'] = None
            from caches import get_pika_redis, redis_shows_copy_key
            redis = get_pika_redis()
            data = redis.hget(redis_shows_copy_key, str(show.id))
            if data:
                data = json.loads(data)
                data['notice'] = data.get('watching_notice')
        return data

    def get_code_list(self, obj):
        qs = TicketUserCode.objects.filter(order=obj)
        data = TicketUserCodeSerializer(qs, many=True, context=self.context).data
        return data

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.snapshot)
        if snapshot.get('price_list'):
            for dd in snapshot['price_list']:
                if dd.get('layers'):
                    layer = dd.get('layers')
                    vl = VenuesLayers.objects.filter(venue=obj.venue, layer=int(layer)).first()
                    if vl:
                        dd['layer_name'] = vl.name
        sc = SessionChangeRecord.objects.filter(session=obj.session).first()
        if sc:
            snapshot['start_at'] = sc.new_start_at.strftime('%Y-%m-%d %H:%M')
            snapshot['end_at'] = sc.new_end_at.strftime('%Y-%m-%d %H:%M')
        return snapshot

    class Meta:
        model = TicketOrder
        fields = TicketOrderSerializer.Meta.fields + ['session', 'code_list', 'show_data']


class TicketOrderDetailNewSerializer(TicketOrderDetailSerializer):
    real_name_list = serializers.SerializerMethodField()
    promotion_amount_list = serializers.SerializerMethodField()

    def get_real_name_list(self, obj):
        if hasattr(obj, 'real_name_order'):
            qs = obj.real_name_order.all()
        else:
            qs = TicketOrderRealName.objects.none()
        data = TicketOrderRealNameSerializer(qs, many=True, context=self.context).data
        return data

    def get_code_list(self, obj):
        qs = TicketUserCode.objects.filter(order=obj)
        data = TicketUserCodeNewSerializer(qs, many=True, context=self.context).data
        return data

    def get_promotion_amount_list(self, obj):
        qs = obj.discount_order.all()
        data = TicketOrderDiscountSerializer(qs, many=True, context=self.context).data
        return data

    class Meta:
        model = TicketOrder
        fields = TicketOrderDetailSerializer.Meta.fields + ['real_name_list', 'promotion_amount_list']


class TicketUserCodeCySerializer(TicketUserCodeSerializer):
    session_seat = serializers.SerializerMethodField()
    code_img_data = serializers.SerializerMethodField()

    def get_session_seat(self, obj):
        return None

    def get_code_img_data(self, obj):
        request = self.context.get('request')
        cy_code = obj.cy_code
        url = None
        if cy_code.check_in_type == 1:
            if cy_code.check_in_code_img:
                url = request.build_absolute_uri(cy_code.check_in_code_img.url)
        elif cy_code.check_in_type == 3:
            url = cy_code.check_in_code
        return dict(url=url, code=cy_code.ticket_no, can_share=True,
                    deadline_at=None, deadline_timestamp=None)

    class Meta:
        model = TicketUserCode
        fields = TicketUserCodeSerializer.Meta.fields + ['code_img_data']


class CyTicketOrderDetailSerializer(TicketOrderDetailNewSerializer):
    cy_exchange = serializers.SerializerMethodField()

    def get_cy_exchange(self, obj):
        from caiyicloud.serializers import CyOrderBasicSerializer
        return CyOrderBasicSerializer(obj.cy_order, context=self.context).data

    def get_code_list(self, obj):
        qs = TicketUserCode.objects.filter(order=obj)
        data = TicketUserCodeCySerializer(qs, many=True, context=self.context).data
        return data

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.snapshot)
        return snapshot

    class Meta:
        model = TicketOrder
        fields = TicketOrderDetailNewSerializer.Meta.fields + ['cy_exchange']


class TicketOrderMarginCreateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(required=True, max_digits=9, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise CustomAPIException('补差金额必须大于0')
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        from caches import get_redis
        redis = get_redis()
        user_key = 'margin_order_key_{}'.format(request.user.id)
        if redis.setnx(user_key, 1):
            # 防止用户重复下单
            redis.expire(user_key, 5)
        else:
            raise CustomAPIException('请勿点击太快')
        try:
            order = TicketOrder.objects.filter(id=validated_data['id'], user_id=request.user.id,
                                               status__in=[TicketOrder.STATUS_PAID, TicketOrder.STATUS_FINISH]).get()
            data = dict(user=order.user, agent=order.agent, u_user_id=order.u_user_id, u_agent_id=order.u_agent_id,
                        title=order.title, session=order.session, venue=order.venue, name=order.name,
                        mobile=order.mobile, multiply=1, amount=validated_data['amount'],
                        actual_amount=validated_data['amount'], order_type=TicketOrder.TY_MARGIN,
                        pay_type=Receipt.PAY_WeiXin_LP, wx_pay_config=order.session.show.wx_pay_config,
                        start_at=order.start_at, end_at=order.end_at, snapshot=order.snapshot, source_order=order)
            inst = TicketOrder.objects.create(**data)
            receipt = Receipt.objects.create(amount=inst.actual_amount, user=order.user, pay_type=inst.pay_type,
                                             biz=Receipt.BIZ_TICKET, wx_pay_config=inst.wx_pay_config)
            inst.receipt = receipt
            inst.save(update_fields=['receipt'])
            return inst
        except TicketOrder.DoesNotExist:
            raise CustomAPIException('订单未支付不能补差')

    class Meta:
        model = TicketOrder
        fields = ['id', 'amount', 'receipt']
        read_only_fields = ['receipt']


class ShowUserSerializer(PKtoNoSerializer):
    id_card = serializers.SerializerMethodField()

    def get_id_card(self, obj):
        return s_id_card(obj.id_card) if obj.id_card else None

    class Meta:
        model = ShowUser
        fields = PKtoNoSerializer.Meta.fields + ['name', 'id_card', 'create_at', 'mobile']


class ShowUserCreateSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False)
    id_card = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_mobile(self, value):
        import re
        REG_MOBILE = r'^\d{11}$'
        R_MOBILE = re.compile(REG_MOBILE)
        if not R_MOBILE.match(value):
            raise CustomAPIException('手机号格式不对')
        return value

    def create(self, validated_data):
        # log.debug(validated_data)
        request = self.context.get('request')
        id_card = validated_data.get('id_card', None)
        if not id_card:
            raise CustomAPIException('请输入身份证号')
        pk = validated_data.get('id')
        if id_card and not pk:
            # 是否已经验证过了，验证过的不需要再验证
            has_auth = ShowUser.objects.filter(id_card=id_card, name=validated_data['name']).first()
            if not has_auth:
                auth_st = ShowUser.auth_cert_no(validated_data['name'], validated_data['id_card'])
                if not auth_st:
                    raise CustomAPIException('姓名与身份证不匹配或有误，请核对后重试！')
        try:
            if pk:
                inst = ShowUser.objects.filter(no=pk).first()
                inst.name = validated_data['name']
                inst.mobile = validated_data['mobile']
                inst.save(update_fields=['name', 'mobile'])
            else:
                inst = ShowUser.objects.create(user=request.user, id_card=validated_data['id_card'],
                                               name=validated_data['name'], mobile=validated_data['mobile'])
        except Exception as e:
            raise CustomAPIException('不能重复添加常用联系人')
        return inst

    class Meta:
        model = ShowUser
        fields = ['id', 'name', 'id_card', 'mobile']


class PerformerFocusRecordSerializer(serializers.ModelSerializer):
    performer = ShowPerformerSerializer()

    class Meta:
        model = PerformerFocusRecord
        fields = ['performer', 'is_collect', 'create_at']


class ShowCommentImageCreateSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=True)

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user_id'] = request.user.id
        r = ShowCommentImage.objects.create(**validated_data)
        return r

    class Meta:
        model = ShowCommentImage
        fields = ['id', 'image']


class ShowCommentImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowCommentImage
        fields = ['id', 'record_id', 'image', 'user_id']


class ShowCommentCreateSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(required=True)
    show_id = serializers.CharField(required=True)
    img_ids = serializers.ListField(required=False)

    def validate_show_id(self, value):
        try:
            show = ShowProject.objects.get(no=value)
            return show
        except ShowProject.DoesNotExist:
            raise CustomAPIException('找不到演出')

    def validate_order_id(self, value):
        try:
            user = self.context.get('request').user
            show = TicketOrder.objects.get(order_no=value, user_id=user.id)
            return show
        except TicketOrder.DoesNotExist:
            raise CustomAPIException('没有权限评论')

    @atomic
    def create(self, validated_data):
        request = self.context.get('request')
        img_ids = validated_data.pop('img_ids', None)
        show = validated_data['show_id']
        order = validated_data['order_id']
        inst = ShowComment.create_record(show, order, validated_data['content'], request.user)
        if img_ids:
            ShowCommentImage.objects.filter(id__in=img_ids).update(record=inst)
        return inst

    class Meta:
        model = ShowComment
        fields = ['order_id', 'show_id', 'content', 'img_ids']


class ShowCommentSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    images = serializers.SerializerMethodField()

    def get_images(self, obj):
        qs = ShowCommentImage.objects.filter(record_id=obj.id)
        return ShowCommentImageSerializer(qs, many=True, context=self.context).data

    class Meta:
        model = ShowComment
        fields = ['user', 'create_at', 'content', 'is_quality', 'images', 'start_at', 'title']


class TicketOrderChangePriceSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(required=True)
    amount = serializers.DecimalField(required=True, max_digits=9, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise CustomAPIException('金额需大于0')
        return value

    def validate_order_id(self, value):
        try:
            return TicketOrder.objects.get(order_no=value, status=TicketOrder.STATUS_UNPAID)
        except TicketOrder.DoesNotExist:
            raise CustomAPIException('修改失败,未付款状态订单才能修改金额')

    @atomic
    def create(self, validated_data):
        # log.error(validated_data)
        request = self.context.get('request')
        from caches import get_redis
        redis = get_redis()
        user_key = 'change_price_key_{}'.format(request.user.id)
        if redis.setnx(user_key, 1):
            # 防止用户重复下单
            redis.expire(user_key, 5)
        else:
            raise CustomAPIException('请勿点击太快')
        return TicketOrderChangePrice.create_record(user=request.user, order=validated_data['order_id'],
                                                    after_amount=validated_data['amount'])

    class Meta:
        model = TicketOrderChangePrice
        fields = ['order_id', 'amount']


class TicketCheckCodeSerializer(serializers.ModelSerializer):
    session_id = serializers.CharField(required=True)
    code = serializers.CharField(required=True)

    def create(self, validated_data):
        request = self.context.get('request')
        code = TicketUserCode.check_t_code(validated_data['code'])
        if not code:
            log.debug('无效二维码{}'.format(validated_data['code']))
            raise CustomAPIException('二维码无效，请刷新再试')
        return TicketUserCode.check_code(request.user, validated_data['session_id'], code)

    class Meta:
        model = TicketUserCode
        fields = ['session_id', 'code']


class TicketCheckOrderCodeSerializer(serializers.ModelSerializer):
    session_id = serializers.CharField(required=True)
    code = serializers.CharField(required=True)

    def create(self, validated_data):
        request = self.context.get('request')
        code = TicketUserCode.check_t_code(validated_data['code'])
        if not code:
            log.debug('无效二维码{}'.format(validated_data['code']))
            raise CustomAPIException('二维码无效，请刷新再试')
        return TicketUserCode.check_code_order(request.user, validated_data['session_id'],
                                               code)

    class Meta:
        model = TicketUserCode
        fields = ['session_id', 'code']


class TicketBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketBooking
        fields = ['id', 'status']


class TicketBookingSetStatusSerializer(serializers.ModelSerializer):
    out_book_no = serializers.CharField(required=True)
    status = serializers.IntegerField(required=True)

    def validate_out_book_no(self, value):
        try:
            user = self.context.get('request').user
            booking = TicketBooking.objects.get(out_book_no=value, user=user)
            return booking
        except TicketBooking.DoesNotExist:
            raise CustomAPIException('找不到记录')

    def create(self, validated_data):
        booking = validated_data.pop('out_book_no')
        booking.set_status(validated_data['status'], validated_data.get('err_msg'), validated_data.get('err_logid'),
                           validated_data.get('book_id'))
        return booking

    class Meta:
        model = TicketBooking
        fields = ['out_book_no', 'err_msg', 'err_logid', 'status', 'book_id']


class TicketGiveRecordSerializer(PKtoNoSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')

    class Meta:
        model = TicketGiveRecord
        fields = PKtoNoSerializer.Meta.fields + ['order', 'mobile', 'give_mobile', 'status', 'status_display',
                                                 'create_at', 'cancel_at',
                                                 'receive_at']


class SessionInfoGiveSerializer(PKtoNoSerializer):
    start_at = serializers.SerializerMethodField()
    end_at = serializers.SerializerMethodField()

    def get_start_at(self, obj):
        return obj.start_at.strftime("%Y-%m-%d %H:%M")

    def get_end_at(self, obj):
        return obj.end_at.strftime("%Y-%m-%d %H:%M")

    class Meta:
        model = SessionInfo
        fields = PKtoNoSerializer.Meta.fields + ['start_at', 'end_at']


class TicketGiveRecordDetailSerializer(TicketGiveRecordSerializer):
    code_list = serializers.SerializerMethodField()
    session = serializers.SerializerMethodField()
    snapshot = serializers.SerializerMethodField()

    def get_code_list(self, obj):
        qs = TicketGiveDetail.objects.filter(record_id=obj)
        data = []
        for inst in qs:
            t_code = inst.ticket_code
            data.append(json.loads(t_code.snapshot))
        return data

    def get_session(self, obj):
        return SessionInfoGiveSerializer(obj.order.session, context=self.context).data

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.order.snapshot)
        return snapshot

    class Meta:
        model = TicketGiveRecord
        fields = TicketGiveRecordSerializer.Meta.fields + ['code_list', 'session', 'snapshot']


class TicketGiveRecordCreateSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(required=True)
    code_ids = serializers.ListField(required=True)
    give_mobile = serializers.CharField(required=True)

    @atomic
    def create(self, validated_data):
        user = self.context.get('request').user
        num = len(validated_data['code_ids'])
        qs = TicketUserCode.objects.filter(order__order_no=validated_data['order_id'], give_id=0,
                                           code__in=validated_data['code_ids'],
                                           order__express_status=TicketOrder.EXPRESS_DEFAULT,
                                           order__user_id=user.id, status=TicketUserCode.STATUS_DEFAULT)
        if not qs or qs.count() != num:
            raise CustomAPIException('只有未使用且未赠送的票才能赠送')
        inst = TicketGiveRecord.create_record(user, validated_data['give_mobile'], qs)
        qs.update(give_status=TicketUserCode.GIVE_UNCLAIMED, give_mobile=validated_data['give_mobile'], give_id=inst.id)
        return inst

    class Meta:
        model = TicketGiveRecord
        fields = ['order_id', 'give_mobile', 'code_ids']


class TicketOrderGiveDetailSerializer(serializers.ModelSerializer):
    basic_info = serializers.SerializerMethodField()
    session = SessionInfoSerializer()
    content = serializers.SerializerMethodField()
    snapshot = serializers.SerializerMethodField()
    venue = VenuesOrderSerializer()

    def get_content(self, obj):
        return obj.session.show.content if obj.session and obj.session.show else None

    def get_snapshot(self, obj):
        snapshot = json.loads(obj.snapshot)
        if snapshot.get('price_list'):
            for dd in snapshot['price_list']:
                if dd.get('layers'):
                    layer = dd.get('layers')
                    vl = VenuesLayers.objects.filter(venue=obj.venue, layer=int(layer)).first()
                    if vl:
                        dd['layer_name'] = vl.name
        sc = SessionChangeRecord.objects.filter(session=obj.session).first()
        if sc:
            snapshot['start_at'] = sc.new_start_at.strftime('%Y-%m-%d %H:%M')
            snapshot['end_at'] = sc.new_end_at.strftime('%Y-%m-%d %H:%M')
        return snapshot

    def get_basic_info(self, obj):
        data = dict()
        from common.utils import s_name, s_mobile, show_content
        data['name'] = s_name(obj.name)
        data['mobile'] = s_mobile(obj.mobile)
        data['id_card'] = show_content(obj.id_card) if obj.id_card else None
        data['order_no'] = show_content(obj.order_no)
        data['status_display'] = obj.get_status_display()
        data['status'] = obj.status
        data['order_type'] = obj.order_type
        return data

    class Meta:
        model = TicketOrder
        fields = ['id', 'session', 'content', 'snapshot', 'basic_info', 'venue']


# 后端不用改
class TicketOrderLockSeatSerializer(serializers.ModelSerializer):
    session_id = serializers.CharField(required=True)
    order_id = serializers.IntegerField(required=True)
    seat_ids = serializers.ListField(required=True)

    @atomic
    def create(self, validated_data):
        from caches import with_redis, session_seat_key, lock_seat_key
        main_session_id = validated_data['session_id']
        order_id = validated_data['order_id']
        user = self.context.get('request').user
        can_lock = True
        lock_seat_key = lock_seat_key.format(user.id)
        with with_redis() as redis:
            if redis.setnx(lock_seat_key, 1):
                redis.expire(lock_seat_key, 3)
                try:
                    order = TicketOrder.objects.get(id=order_id)
                except TicketOrder.DoesNotExist:
                    raise CustomAPIException('找不到订单')
                if order.is_lock_seat:
                    raise CustomAPIException('订单已完成出票，请勿重复操作！')
                code_qs = TicketUserCode.objects.filter(order_id=order_id, session_id=order.session_id)
                num = code_qs.count()
                if code_qs.count() != len(validated_data['seat_ids']):
                    raise CustomAPIException('请选择正确的座位数量，数量{}'.format(num))
                seat_qs = SessionSeat.objects.filter(session__no=main_session_id, id__in=validated_data['seat_ids'])
                for seat in seat_qs:
                    kk = session_seat_key.format(seat.ticket_level.id, seat.id)
                    # 是否可卖，锁着的也可以手动出票
                    if not seat.is_buy and not seat.order_no:
                        if not redis.setnx(kk, 1):
                            can_lock = False
                            break
                        else:
                            redis.expire(kk, 30)
                    else:
                        can_lock = False
                        break
                if not can_lock:
                    # 失败就全部删掉锁
                    for seat in seat_qs:
                        kk = session_seat_key.format(seat.ticket_level.id, seat.id)
                        redis.delete(kk)
                    raise CustomAPIException('找不到满足条件的座位')
                else:
                    i = 0
                    code_list = list(code_qs)
                    for session_seat in seat_qs:
                        session_seat.set_buy()
                        # 写入订单号
                        session_seat.order_no = order.order_no
                        session_seat.change_pika_redis(is_buy=True, can_buy=False, order_no=order.order_no)
                        # 座位写到旧的无座订单码上面
                        code_inst = code_list[i]
                        code_inst.session_seat = session_seat
                        i += 1
                    SessionSeat.objects.bulk_update(list(seat_qs), ['order_no'])
                    TicketUserCode.objects.bulk_update(code_list, ['session_seat'])
                    order.set_lock_seats(True)
                    # 发短信
                    data = dict(biz='lock_seat', name=order.title, mobile=order.mobile, code='web',
                                time=order.session.start_at.strftime("%Y-%m-%d %H:%M"))
                    from qcloud.sms import get_sms
                    sms = get_sms()
                    try:
                        sms.smsvrcode(data)
                    except Exception as e:
                        log.error(e)
            else:
                raise CustomAPIException('请勿操作太快')

    class Meta:
        model = SessionInfo
        fields = ['session_id', 'order_id', 'seat_ids']


class ShowAiSerializer(serializers.ModelSerializer):
    venues = VenuesAiSerializer()
    show_type = ShowTypeBasicSerializer()

    class Meta:
        model = ShowProject
        fields = ['no', 'logo_mobile', 'title', 'price', 'venues', 'show_type']


class ShowIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowProject
        fields = ['no', 'logo_mobile', 'price', 'title']


class ShowContentCategoryHomeSerializer(serializers.ModelSerializer):
    cate_id = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()

    def get_cate_id(self, obj):
        return obj.pk

    def get_data(self, obj):
        data = obj.get_index_data(self.context)
        return data

    class Meta:
        model = ShowContentCategory
        fields = ['cate_id', 'title', 'en_title', 'data']


class TicketWatchingNoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketWatchingNotice
        fields = ['title', 'content']


class TicketPurchaseNoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketPurchaseNotice
        fields = ['title', 'content']
