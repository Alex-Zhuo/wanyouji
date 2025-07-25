from django.views.decorators.cache import cache_page
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import viewsets, views

from home.views import ReturnNoDetailViewSet, DetailPKtoNoViewSet, ReturnNoneViewSet
from mall.views import ReceiptViewset
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.mixins import SerializerSelector
from restframework_ext.permissions import IsPermittedUser, IsPermittedAgentUser, IsPermittedStaffUser, IsSuperUser, \
    IsTicketUser, IsPermittedManagerUser, IsStaffUser, IsLockSeatUser
from restframework_ext.pagination import StandardResultsSetPagination, DefaultNoPagePagination
from ticket.models import Seat, Venues, TicketColor, ShowProject, ShowCollectRecord, SessionSeat, TicketOrder, \
    SessionInfo, TicketFile, PerformerFocusRecord, ShowPerformer, ShowType, ShowUser, TicketUserCode, tiktok_goods_url, \
    tiktok_order_detail_url, TicketOrderRefund, ShowComment, ShowCommentImage, TicketBooking, TicketGiveRecord, \
    TicketGiveDetail
from ticket.serializers import VenuesSerializer, TicketColorSerializer, SeatCreateSerializer, ShowProjectSerializer, \
    ShowProjectDetailSerializer, ShowCollectRecordSerializer, SessionSeatSerializer, TicketOrderSerializer, \
    SessionInfoSerializer, SessionInfoDetailSerializer, TicketFileCreateSerializer, \
    TicketFileSerializer, TicketFileChangeSerializer, SessionSeatCreateSerializer, TicketOrderDetailSerializer, \
    VenuesDetailSerializer, ShowPerformerSerializer, ShowPerformerDetailSerializer, ShowTypeSerializer, \
    ShowProjectRecommendSerializer, ShowUserSerializer, ShowUserCreateSerializer, PerformerFocusRecordSerializer, \
    ShowPerformerRecommendSerializer, ShowProjectStatisticsSerializer, \
    SessionCopySerializer, TicketFileBackSerializer, SessionInfoEditDetailSerializer, \
    ShowCommentCreateSerializer, ShowCommentImageSerializer, ShowCommentImageCreateSerializer, ShowCommentSerializer, \
    TicketCheckCodeSerializer, TicketCheckOrderCodeSerializer, ShowProjectStaffNewSerializer, TicketBookingSerializer, \
    TicketBookingSetStatusSerializer, TicketOrderChangePriceSerializer, \
    SessionInfoStaffDetailSerializer, TicketOrderMarginCreateSerializer, SessionSearchListSerializer, \
    SessionExpressFeeSerializer, TicketGiveRecordCreateSerializer, TicketGiveRecordSerializer, \
    TicketGiveRecordDetailSerializer, TicketOrderGiveDetailSerializer, \
    TicketOrderLockSeatSerializer, TicketOrderDetailNewSerializer, TicketUserCodeNewSerializer, ShowAiSerializer, \
    VenuesCustomerDetailSerializer
from restframework_ext.exceptions import CustomAPIException
from django.utils import timezone
from django.db.models import Max, Min
import json
import os
from django.db.models import Q
import logging
from django.db.transaction import atomic
from django.http.response import HttpResponse, Http404
from datetime import timedelta
from decimal import Decimal
import requests
from common.utils import get_config, sha256_str
from datetime import datetime
import time
from django.core.cache import cache
from django.utils.decorators import method_decorator
from ticket.serializers import get_origin
from caches import get_prefix
from ticket.order_serializer import ticket_order_dispatch
log = logging.getLogger(__name__)

PREFIX = get_prefix()


class TicketReceiptViewSet(ReceiptViewset):
    permission_classes = []
    refund_class = TicketOrderRefund


class VenuesViewSet(SerializerSelector, DetailPKtoNoViewSet):
    queryset = Venues.objects.filter(is_use=True)
    serializer_class = VenuesSerializer
    serializer_class_retrieve = VenuesCustomerDetailSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']

    def list(self, request, *args, **kwargs):
        queryset = self.queryset
        kw = request.GET.get('kw')
        city = request.GET.get('city')
        lng = request.GET.get('lng') or None
        lat = request.GET.get('lat') or None
        if kw:
            queryset = queryset.filter(name__contains=kw)
        if city:
            queryset = queryset.filter(city_id=int(city))
        try:
            if lng and lat and queryset:
                from ticket.utils import get_locations_queryset
                queryset = get_locations_queryset(queryset, float(lng), float(lat))
            page = self.paginate_queryset(queryset)
            return self.get_paginated_response(
                self.serializer_class(page, many=True, context={'request': request}).data)
        except Exception as e:
            log.error(e)
            raise CustomAPIException('场馆地址未更新，请联系管理员！')

    @action(methods=['post'], detail=False, permission_classes=[IsSuperUser])
    def set_seat(self, request):
        s = SeatCreateSerializer(data=request.data, context=dict(request=request))
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()

    @action(methods=['get'], detail=False, permission_classes=[])
    def recommend(self, request):
        lng = request.GET.get('lng') or None
        lat = request.GET.get('lat') or None
        queryset = self.queryset.order_by('display_order')
        try:
            if lng and lat and queryset:
                from ticket.utils import get_locations_queryset
                queryset = get_locations_queryset(queryset, float(lng), float(lat))
            qs = queryset[0:6]
            data = VenuesSerializer(qs, many=True, context={'request': request}).data
            return Response(data)
        except Exception as e:
            log.error(e)
            raise CustomAPIException('场馆地址未更新，请联系管理员！')

    @action(methods=['get'], detail=True)
    def get_shows(self, request, pk):
        queryset = ShowProject.objects.filter(venues__no=pk, status=ShowProject.STATUS_ON)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(ShowProjectSerializer(page, many=True, context={'request': request}).data)

    @action(methods=['get'], detail=True, permission_classes=[IsTicketUser])
    def back_detail(self, request, pk):
        inst = self.get_object()
        data = VenuesDetailSerializer(inst, context={'request': request}).data
        return Response(data)

    @action(methods=['get'], detail=False)
    def map_geocoder(self, request):
        from common.config import get_config
        name = request.GET.get('address') or '广州市'
        gaodekey = get_config()['gaodekey']
        url = 'https://restapi.amap.com/v3/geocode/geo?address={}&key={}'.format(name, gaodekey)
        resp = requests.get(url)
        return HttpResponse(resp)

    @action(methods=['get'], detail=False)
    def map_search(self, request):
        from common.config import get_config
        name = request.GET.get('name') or '深圳市'
        baidukey = get_config()['baidukey']
        # false 不需要填城市
        url = 'http://api.map.baidu.com/place/v2/suggestion?query={}&region={}&city_limit={}&output=json&ak={}'.format(
            name, 1, False, baidukey)
        resp = requests.get(url)
        return Response(data=resp.text)


class TicketColorViewSet(viewsets.ModelViewSet):
    queryset = TicketColor.objects.filter(is_use=True)
    serializer_class = TicketColorSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']


class ShowProjectViewSet(SerializerSelector, DetailPKtoNoViewSet):
    queryset = ShowProject.objects.filter(status=ShowProject.STATUS_ON)
    serializer_class = ShowProjectSerializer
    serializer_class_retrieve = ShowProjectDetailSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']

    def retrieve(self, request, *args, **kwargs):
        # log.debug('retrieve')
        from caches import get_pika_redis, redis_shows_copy_key, show_collect_copy_key, redis_shows_no_key
        no = kwargs['pk']
        with get_pika_redis() as pika:
            show_id = pika.hget(redis_shows_no_key, no)
        if not show_id:
            show = self.get_object()
            show.set_shows_no_pk()
            show_id = show.id
        # show_id = kwargs['pk']
        is_tiktok, is_ks, is_xhs = get_origin(request)
        name = '{}_{}{}'.format(show_id, int(is_tiktok), int(is_ks), int(is_xhs))
        from caches import cache_show_detail_key
        key = cache_show_detail_key.format(name)
        data = cache.get(key)
        if data:
            with get_pika_redis() as pika:
                nn = '{}_{}'.format(request.user.id, show_id)
                is_collect = pika.hget(show_collect_copy_key, nn)
            data['is_collect'] = True if is_collect else False
            return Response(data)
        user = request.user
        with get_pika_redis() as pika:
            data = pika.hget(redis_shows_copy_key, show_id)
            if data:
                data = json.loads(data)
        # log.debug(data)
        if not data:
            raise CustomAPIException('演出项目已下架')
        if data.get('is_test'):
            return super(ShowProjectViewSet, self).retrieve(request, *args, **kwargs)
        else:
            # log.debug(data)
            data = ShowProject.get_cache(data, show_id, user, is_tiktok, is_ks, is_xhs)
            # cache.set(key, data, 60)
            with get_pika_redis() as pika:
                nn = '{}_{}'.format(request.user.id, show_id)
                is_collect = pika.hget(show_collect_copy_key, nn)
            data['is_collect'] = True if is_collect else False
            # log.debug('end_retrieve')
            return Response(data)

    @method_decorator(cache_page(90, key_prefix=PREFIX))
    def list(self, request, *args, **kwargs):
        # log.debug('开始加载项目')
        queryset = self.queryset
        title = request.GET.get('title') or None
        cate_id = request.GET.get('cate_id') or None
        start_at = request.GET.get('start_at') or None
        price = request.GET.get('price') or None
        show_at = request.GET.get('show_at') or None
        # province = request.GET.get('province')
        city = request.GET.get('city') or None
        # 演出日历展示当天的
        date_at = request.GET.get('date_at') or None
        lng = request.GET.get('lng') or None
        lat = request.GET.get('lat') or None
        type_id = request.GET.get('type_id') or None
        is_schedule = request.GET.get('is_schedule') or None
        if type_id:
            queryset = queryset.filter(show_type_id=int(type_id))
        if title:
            queryset = queryset.filter(title__contains=title)
        if show_at:
            queryset = queryset.filter(session_info__status=SessionInfo.STATUS_ON,
                                       session_info__end_at__gte=show_at).distinct()
        if date_at:
            from common.dateutils import date_from_str
            date_at = date_from_str(date_at)
            date_tomorrow_at = date_at + timedelta(days=1)
            queryset = queryset.filter(session_info__status=SessionInfo.STATUS_ON,
                                       session_info__start_at__gte=date_at,
                                       session_info__start_at__lte=date_tomorrow_at).distinct()
        if city:
            # from express.models import Division
            # ct = Division.objects.filter(type=Division.TYPE_CITY, city__contains=city,
            #                              county__isnull=True).first()
            # if ct:
            queryset = queryset.filter(city_id=int(city))
        if cate_id:
            queryset = queryset.filter(cate_id=int(cate_id))
        order_desc = None
        if price:
            order_desc = 'price' if price == '1' else '-price'
        # 这里可能查询会慢
        elif start_at:
            queryset = queryset.annotate(sa=Min("session_info__start_at"))
            order_desc = 'sa' if start_at == '1' else '-sa'
        if order_desc:
            queryset = queryset.order_by(order_desc)
        else:
            if lng and lat and queryset:
                from ticket.utils import get_locations_queryset
                # log.debug('计算')
                queryset = get_locations_queryset(queryset, float(lng), float(lat))
                # log.debug('计算结束')
            else:
                queryset = queryset.order_by('-session_end_at')
        # log.error(queryset.count())
        if is_schedule:
            queryset = queryset.order_by('-show_type_id')
        try:
            page = self.paginate_queryset(queryset)
            ret = self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)
            # log.debug('结束加载')
            # from django.db import connection
            # q = connection.queries
            # log.error(q)
            return ret
        except Exception as e:
            log.error(e)
            raise CustomAPIException('场馆地址未更新，请联系管理员！')

    @action(methods=['get'], detail=False)
    def get_calendar(self, request):
        city_id = request.GET.get('city') or 0
        now = timezone.now()
        year = request.GET.get('year') or now.year
        month = request.GET.get('month') or now.month
        is_tiktok, is_ks, is_xhs = get_origin(request)
        data, _, _ = ShowProject.get_show_calendar(city_id=int(city_id), year=int(year), month=int(month),
                                                   is_tiktok=is_tiktok, is_ks=is_ks, is_xhs=is_xhs)
        return Response(data)

    @action(methods=['post'], detail=False)
    def set_comment(self, request):
        s = ShowCommentCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        inst = s.create(s.validated_data)
        return Response(inst.id)

    @method_decorator(cache_page(120, key_prefix=PREFIX))
    @action(methods=['get'], detail=False, permission_classes=[])
    def recent_shows(self, request):
        # log.debug('recent_shows')
        # from caches import get_redis, session_info_recent_qs
        # redis = get_redis()
        # data = redis.get(session_info_recent_qs)
        # if not data:
        city_id = request.GET.get('city')
        lng = request.GET.get('lng') or None
        lat = request.GET.get('lat') or None
        queryset = self.queryset.filter(sale_time__lte=timezone.now(), session_end_at__gt=timezone.now())
        if city_id:
            queryset = queryset.filter(city_id=int(city_id))
        try:
            if lng and lat and queryset:
                from ticket.utils import get_locations_queryset
                queryset = get_locations_queryset(queryset, float(lng), float(lat))
            else:
                queryset = queryset.annotate(sa=Min("session_info__start_at"))
                queryset = queryset.order_by('-display_order', 'sa')[:6]
            data = ShowProjectRecommendSerializer(queryset, many=True, context={'request': request}).data
            #     if data:
            #         redis.set(session_info_recent_qs, json.dumps(data))
            #         redis.expire(session_info_recent_qs, 60)
            # else:
            #     data = json.loads(data)
            return Response(data)
        except Exception as e:
            log.error(e)
            raise CustomAPIException('场馆地址未更新，请联系管理员！')

    @method_decorator(cache_page(120, key_prefix=PREFIX))
    @action(methods=['get'], detail=False, permission_classes=[])
    def recommend_shows(self, request):
        # log.debug('recommend_shows')
        # if not data:
        city_id = request.GET.get('city')
        from caches import get_pika_redis, session_info_recommend_qs
        data = None
        if not city_id:
            with get_pika_redis() as redis:
                data = redis.get(session_info_recommend_qs)
        if data:
            # log.error('not city cache')
            return Response(json.loads(data))
        lng = request.GET.get('lng') or None
        lat = request.GET.get('lat') or None
        queryset = self.queryset.filter(is_recommend=True, sale_time__lte=timezone.now(),
                                        session_end_at__gt=timezone.now())
        if city_id:
            queryset = queryset.filter(city_id=int(city_id))
        try:
            if lng and lat and queryset:
                from ticket.utils import get_locations_queryset
                queryset = get_locations_queryset(queryset, float(lng), float(lat), is_show_type=True)
            else:
                queryset = queryset.annotate(sa=Min("session_info__start_at"))
                queryset = queryset.order_by('-display_order', 'sa')
            data = ShowProjectRecommendSerializer(queryset.order_by('-show_type_id')[:6], many=True,
                                                  context={'request': request}).data
            if data and not city_id:
                with get_pika_redis() as redis:
                    redis.set(session_info_recommend_qs, json.dumps(data))
                    redis.expire(session_info_recommend_qs, 2 * 60)
            return Response(data)
        except Exception as e:
            log.error(e)
            raise CustomAPIException('场馆地址未更新，请联系管理员！')

    @action(methods=['post'], detail=True)
    def collect(self, request, pk):
        show = self.get_object()
        ShowCollectRecord.create_record(request.user, show)
        return Response()

    @action(methods=['get'], detail=False)
    def get_type(self, request):
        qs = ShowType.objects.filter(is_use=True)
        data = ShowTypeSerializer(qs, many=True).data
        return Response(data)

    @action(methods=['get'], detail=True)
    def shows_wxa_code(self, request, pk):
        """
        邀请代理的小程序码
        :param request:
        :return:
        """
        show = self.get_object()
        user = request.user
        from mall.utils import qrcode_dir_pro
        from urllib.parse import quote
        dir, rel_url = qrcode_dir_pro()
        tiktok, is_ks, is_xhs = get_origin(request)
        if tiktok:
            nn = 'tiktok{}'.format(show.pk)
        elif is_ks:
            nn = 'ks{}'.format(show.pk)
        elif is_xhs:
            nn = 'xhs{}'.format(show.pk)
        else:
            nn = show.pk
        filename = 'show_{}_{}_13v{}.png'.format(nn, user.id, show.version)
        filepath = os.path.join(dir, filename)
        log.error(filename)
        if not os.path.isfile(filepath):
            url = 'pages/pagesKage/showDetail/showDetail'
            is_img = False
            if is_ks:
                url = '{}?share_code={}&id={}'.format(url, user.share_code, pk)
                url = quote('/{}'.format(url), safe='')
                from kuaishou_wxa.api import get_ks_wxa
                ks_wxa = get_ks_wxa()
                ks_url = 'kwai://miniapp?appId={}&KSMP_source={}&KSMP_internal_source={}&path={}'.format(ks_wxa.app_id,
                                                                                                         '011012',
                                                                                                         '011012', url)
                from common import qrutils
                buf = qrutils.generate(ks_url, size=(410, 410))
                is_img = True
            else:
                if tiktok:
                    from douyin import get_tiktok
                    tk = get_tiktok()
                    url = '{}?share_code={}&id={}'.format(url, user.share_code, pk)
                    buf = tk.get_qrcode(url)
                elif is_xhs:
                    from xiaohongshu.api import get_xhs_wxa
                    xhs_wxa = get_xhs_wxa()
                    scene = 'sg_%s_%s' % (show.pk, user.share_code)
                    buf = xhs_wxa.get_qrcode_unlimited(scene, url)
                else:
                    from mp.wechat_client import get_wxa_client
                    wxa = get_wxa_client()
                    scene = 'sg_%s_%s' % (show.pk, user.share_code)
                    # url = 'pages/pagesKage/showDetail/showDetail'
                    buf = wxa.biz_get_wxa_code_unlimited(scene, url)
            if buf:
                from common.qrutils import show_share_wxa_code
                flag = show.flag.filter(img__isnull=False).first()
                show_share_wxa_code(buf, filepath, show, flag.img.path if flag and flag.img else None, is_img)
            else:
                raise CustomAPIException('获取失败')
        url = request.build_absolute_uri('/'.join([rel_url, filename]))
        return Response(data=dict(url=url))

    # @action(methods=['get'], detail=False, permission_classes=[IsPermittedStaffUser])
    # def staff_record(self, request):
    #     queryset = self.queryset.filter(sale_time__lte=timezone.now(), session_end_at__gt=timezone.now())
    #     title = request.GET.get('title')
    #     city = request.GET.get('city')
    #     if title:
    #         queryset = queryset.filter(title__contains=title)
    #     if city:
    #         queryset = queryset.filter(city_id=int(city))
    #     if request.user.account.venue.all():
    #         ids_list = list(request.user.account.venue.all().values_list('id', flat=True))
    #         if ids_list:
    #             ids = None
    #             for dd in ids_list:
    #                 if not ids:
    #                     ids = str(dd)
    #                 else:
    #                     ids = '{},{}'.format(ids, str(dd))
    #             ordering = 'FIELD(`venues_id`, {})'.format(ids)
    #             queryset = queryset.extra(select={'ordering': ordering}, order_by=('-ordering',))
    #     page = self.paginate_queryset(queryset)
    #     return self.get_paginated_response(
    #         ShowProjectStaffSerializer(page, many=True, context={'request': request}).data)

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedStaffUser])
    def staff_record_new(self, request):
        queryset = self.queryset.filter(sale_time__lte=timezone.now(), session_end_at__gt=timezone.now())
        title = request.GET.get('title')
        city = request.GET.get('city')
        if title:
            queryset = queryset.filter(title__contains=title)
        if city:
            queryset = queryset.filter(city_id=int(city))
        if request.user.account.venue.all():
            ids_list = list(request.user.account.venue.all().values_list('id', flat=True))
            if ids_list:
                ids = None
                for dd in ids_list:
                    if not ids:
                        ids = str(dd)
                    else:
                        ids = '{},{}'.format(ids, str(dd))
                ordering = 'FIELD(`venues_id`, {})'.format(ids)
                queryset = queryset.extra(select={'ordering': ordering}, order_by=('-ordering',))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(
            ShowProjectStaffNewSerializer(page, many=True, context={'request': request}).data)

    @method_decorator(cache_page(60, key_prefix=PREFIX))
    @action(methods=['get'], detail=False, permission_classes=[IsPermittedStaffUser])
    def statistics(self, request):
        queryset = ShowProject.objects.all()
        status = request.GET.get('status')
        # status 1 未结束 2已结束
        title = request.GET.get('title')
        city = request.GET.get('city')
        if city:
            queryset = queryset.filter(city_id=int(city))
        if title:
            queryset = queryset.filter(title__contains=title)
        if status:
            status = int(status)
            if status == 1:
                queryset = queryset.filter(sale_time__lte=timezone.now(), session_end_at__gt=timezone.now())
            else:
                queryset = queryset.filter(session_end_at__lte=timezone.now())
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(
            ShowProjectStatisticsSerializer(page, many=True, context={'request': request}).data)

    @method_decorator(cache_page(60, key_prefix=PREFIX))
    @action(methods=['get'], detail=True, permission_classes=[IsPermittedStaffUser])
    def statistics_detail(self, request, pk):
        try:
            show = ShowProject.objects.get(no=pk)
            queryset = SessionInfo.objects.filter(show=show, is_delete=False)
            page = self.paginate_queryset(queryset)
            return self.get_paginated_response(
                SessionInfoStaffDetailSerializer(page, many=True, context={'request': request}).data)
        except ShowProject.DoesNotExist:
            raise CustomAPIException('找不到场次')

    @action(methods=['get'], detail=False)
    def tiktok_template_ids(self, request):
        from douyin import TikTokWxa
        template_ids = [TikTokWxa.SHOW_START_TEMPLATE_ID]
        return Response(template_ids)

    @action(methods=['post'], detail=False)
    def get_ai_list(self, request):
        no_list = request.data.get('no_list')
        qs = ShowProject.objects.filter(no__in=no_list)
        data = ShowAiSerializer(qs, context={'request': request}, many=True).data
        return Response(data)


class SessionSeatViewSet(ReturnNoDetailViewSet):
    queryset = SessionSeat.objects.none()
    serializer_class = SessionSeatSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        session_id = request.GET.get('session_id')
        if not session_id:
            raise CustomAPIException('session_id必传')
        from caches import get_pika_redis, pika_session_seat_list_key, redis_session_no_key
        pika = get_pika_redis()
        s_id = pika.hget(redis_session_no_key, session_id)
        if not s_id:
            raise CustomAPIException('未配置座位信息')
        key = pika_session_seat_list_key.format(s_id)
        data = pika.get(key)
        data = json.loads(data) if data else None
        # data = self.serializer_class(seat_qs, many=True, context={'request': request}).data
        return Response(data)

    @action(methods=['get'], detail=False)
    def get_data(self, request):
        session_id = request.GET.get('session_id')
        if not session_id:
            raise CustomAPIException('session_id必传')
        from caches import get_pika_redis, pika_session_seat_key, redis_session_no_key
        pika = get_pika_redis()
        s_id = pika.hget(redis_session_no_key, session_id)
        if not s_id:
            raise CustomAPIException('未配置座位信息')
        key = pika_session_seat_key.format(s_id)
        data = pika.hgetall(key)
        if data:
            return Response(list(data.values()))
        raise CustomAPIException('未配置座位信息')


class SessionInfoViewSet(SerializerSelector, DetailPKtoNoViewSet):
    queryset = SessionInfo.objects.filter(status=ShowProject.STATUS_ON, is_delete=False)
    serializer_class = SessionInfoSerializer
    serializer_class_retrieve = SessionInfoDetailSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']

    @method_decorator(cache_page(60, key_prefix=PREFIX))
    def list(self, request, *args, **kwargs):
        qs = self.queryset
        is_tiktok, is_ks, is_xhs = get_origin(request)
        if is_tiktok:
            qs = qs.filter(dy_status=SessionInfo.STATUS_ON)
        elif is_ks:
            from kuaishou_wxa.models import KsGoodsConfig
            qs = KsGoodsConfig.get_session_qs(qs)
        elif is_xhs:
            from xiaohongshu.models import XhsGoodsConfig
            qs = XhsGoodsConfig.get_session_qs(qs)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    @action(methods=['post'], detail=False, permission_classes=[IsSuperUser])
    def set_price(self, request):
        # log.error(request.data)
        s = SessionSeatCreateSerializer(data=request.data, context=dict(request=request))
        s.is_valid()
        s.create(s.validated_data)
        return Response()

    @action(methods=['get'], detail=True, permission_classes=[IsTicketUser])
    def edit_detail(self, request, pk):
        inst = SessionInfo.objects.get(no=pk)
        data = SessionInfoDetailSerializer(inst, context=dict(request=request)).data
        return Response(data)

    @action(methods=['get'], detail=True, permission_classes=[IsTicketUser])
    def edit_no_seat(self, request, pk):
        inst = SessionInfo.objects.get(no=pk)
        data = SessionInfoEditDetailSerializer(inst, context=dict(request=request)).data
        return Response(data)

    @action(methods=['post'], detail=False, permission_classes=[IsTicketUser])
    def copy_session(self, request):
        # log.warning(request.POST)
        # 后台用id
        s = SessionCopySerializer(data=request.data, context=dict(request=request))
        s.is_valid()
        ret = s.create(s.validated_data)
        return Response(ret)

    @action(methods=['get'], detail=False, permission_classes=[IsStaffUser])
    def get_session_list(self, request):
        kw = request.GET.get('kw')
        qs = SessionInfo.objects.filter(is_delete=False, show__title__contains=kw)
        data = SessionSearchListSerializer(qs, many=True).data
        return Response(data)

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedUser])
    def get_express_fees(self, request):
        s = SessionExpressFeeSerializer(data=request.GET, context=dict(request=request))
        s.is_valid(True)
        ret = s.create(s.validated_data)
        return Response(ret)


# 后台用的接口
class TicketFileViewSet(SerializerSelector, ReturnNoDetailViewSet):
    queryset = TicketFile.objects.none()
    serializer_class = TicketFileSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get', 'post']

    def list(self, request, *args, **kwargs):
        # 前端用no
        session_id = request.GET.get('session_id')
        if not session_id or session_id == 'undefined':
            raise CustomAPIException('场次错误')
        ticket_qs = TicketFile.objects.filter(session__no=session_id)
        data = self.serializer_class(ticket_qs, many=True, context={'request': request}).data
        return Response(data)

    @action(methods=['post'], detail=False, permission_classes=[IsTicketUser])
    def create_record(self, request):
        s = TicketFileCreateSerializer(data=request.data, context=dict(request=request))
        s.is_valid()
        s.create(s.validated_data)
        return Response()

    @action(methods=['post'], detail=False, permission_classes=[IsTicketUser])
    def change_record(self, request):
        s = TicketFileChangeSerializer(data=request.data, context=dict(request=request))
        s.is_valid()
        s.create(s.validated_data)
        return Response()

    @action(methods=['get'], detail=False, permission_classes=[IsTicketUser])
    def back_levels(self, request):
        session_id = request.GET.get('session_id')
        if not session_id or session_id == 'undefined':
            raise CustomAPIException('场次错误')
        ticket_qs = TicketFile.objects.filter(session_id=int(session_id))
        data = TicketFileBackSerializer(ticket_qs, many=True, context={'request': request}).data
        return Response(data)


class ShowCollectRecordViewSet(ReturnNoDetailViewSet):
    queryset = ShowCollectRecord.objects.filter(is_collect=True, show__status=ShowProject.STATUS_ON)
    serializer_class = ShowCollectRecordSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    http_method_names = ['get']


class ShowPerformerViewSet(SerializerSelector, viewsets.ModelViewSet):
    queryset = ShowPerformer.objects.filter(is_show=True)
    serializer_class = ShowPerformerSerializer
    serializer_class_retrieve = ShowPerformerDetailSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']

    # @method_decorator(cache_page(60 * 5, key_prefix=PREFIX))
    def list(self, request, *args, **kwargs):
        kw = request.GET.get('kw')
        queryset = self.queryset
        if kw:
            queryset = queryset.filter(name__contains=kw)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    # @method_decorator(cache_page(60, key_prefix=PREFIX))
    # def retrieve(self, request, *args, **kwargs):
    #     return super(ShowPerformerViewSet, self).retrieve(request, *args, **kwargs)

    @action(methods=['post'], detail=True)
    def do_focus(self, request, pk):
        try:
            inst = self.queryset.get(pk=pk)
            PerformerFocusRecord.create_record(user=request.user, performer=inst)
        except ShowPerformer.DoesNotExist:
            raise CustomAPIException('找不到演员')
        return Response()

    @method_decorator(cache_page(60 * 5, key_prefix=PREFIX))
    @action(methods=['get'], detail=False, permission_classes=[])
    def recommend(self, request):
        qs = self.queryset
        total = qs.count()
        qs = qs[0:6]
        dd = dict()
        data = ShowPerformerRecommendSerializer(qs, many=True, context={'request': request}).data
        dd['total'] = total
        dd['data'] = data
        return Response(dd)


class TicketOrderViewSet(SerializerSelector, ReturnNoDetailViewSet):
    queryset = TicketOrder.objects.all()
    serializer_class = TicketOrderSerializer
    # serializer_class_retrieve = TicketOrderDetailSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    lookup_field = 'order_no'
    lookup_url_kwarg = 'pk'

    def list(self, request, *args, **kwargs):
        kw = request.GET.get('kw')
        status = request.GET.get('status') or None
        qs = self.queryset.filter(user=request.user)
        if status:
            qs = qs.filter(status=int(status))
        if kw:
            qs = qs.filter(Q(order_no=kw) | Q(name__contains=kw) | Q(title__contains=kw))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    @action(methods=['get'], detail=False)
    def give_list(self, request):
        kw = request.GET.get('kw')
        order_ids = TicketGiveRecord.objects.filter(receive_user_id=request.user.id).values_list('order_id',
                                                                                                 flat=True).order_by(
            'order_id').distinct()
        if order_ids:
            qs = self.queryset.filter(id__in=list(order_ids))
            if kw:
                qs = qs.filter(Q(order_no=kw) | Q(name__contains=kw) | Q(title__contains=kw))
        else:
            qs = TicketOrder.objects.none()
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    # @action(methods=['get'], detail=True)
    # def give_detail(self, request, pk):
    #     give_record_list = TicketGiveRecord.objects.filter(order_id=pk, receive_user_id=request.user.id)
    #     if not give_record_list:
    #         raise CustomAPIException('找不到订单')
    #     give_record = give_record_list.first()
    #     data = TicketOrderGiveDetailSerializer(give_record.order, context={'request': request}).data
    #     code_list = []
    #     for record in give_record_list:
    #         qs = TicketGiveDetail.objects.filter(record_id=record.id)
    #         for inst in qs:
    #             code_list.append(TicketUserCodeSerializer(inst.ticket_code, context={'request': request}).data)
    #     data['code_list'] = code_list
    #     return Response(data)

    @action(methods=['get'], detail=False)
    def give_detail_new(self, request):
        order_no = request.GET.get('order_no')
        give_record_list = TicketGiveRecord.objects.filter(order__order_no=order_no, receive_user_id=request.user.id)
        if not give_record_list:
            raise CustomAPIException('找不到订单')
        give_record = give_record_list.first()
        data = TicketOrderGiveDetailSerializer(give_record.order, context={'request': request}).data
        code_list = []
        for record in give_record_list:
            qs = TicketGiveDetail.objects.filter(record_id=record.id)
            for inst in qs:
                code_list.append(TicketUserCodeNewSerializer(inst.ticket_code, context={'request': request}).data)
        data['code_list'] = code_list
        return Response(data)

    @action(methods=['post'], detail=False, permission_classes=[IsLockSeatUser])
    def lock_seats(self, request):
        s = TicketOrderLockSeatSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()

    @action(methods=['get'], detail=True, permission_classes=[IsLockSeatUser])
    def cancel_lock_seats(self, request, pk):
        order = TicketOrder.objects.get(pk=pk)
        order.cancel_lock_seats()
        return Response()

    @action(methods=['get'], detail=True)
    def query_express(self, request, pk):
        # 查看物流
        order = self.get_object()
        express_no = order.express_no
        if order.express_comp_no in ['SFEXPRESS', 'ZTO']:
            express_no = '{}:{}'.format(express_no, order.mobile[-4:])
        from mall.express_api import query_express
        succ, data = query_express(order.express_comp_no, express_no)
        return Response(data) if succ else Response(status=500, data=data)

    @action(methods=['get'], detail=True)
    def express_finish(self, request, pk):
        try:
            order = self.get_object()
            if order.express_status in TicketOrder.can_express_status():
                order.set_express_finish()
            else:
                raise CustomAPIException('订单状态不允许该操作')
        except TicketOrder.DoesNotExist:
            raise CustomAPIException('找不到订单')
        return Response()

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedManagerUser])
    def search_order(self, request):
        kw = request.GET.get('kw')
        qs = self.queryset.filter(status=TicketOrder.STATUS_UNPAID)
        if kw:
            qs = qs.filter(Q(order_no=kw) | Q(mobile=kw))
            data = self.serializer_class(qs, many=True, context={'request': request}).data
            return Response(data)
        return Response()

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedManagerUser])
    def change_amount(self, request):
        s = TicketOrderChangePriceSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        s.create(s.validated_data)
        return Response()

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedStaffUser])
    def check_code(self, request):
        s = TicketCheckCodeSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        status, msg, snapshot = s.create(s.validated_data)
        return Response(dict(status=status, msg=msg, snapshot=snapshot))

    @action(methods=['post'], detail=False, permission_classes=[IsPermittedStaffUser])
    def check_order_code(self, request):
        s = TicketCheckOrderCodeSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        ret = s.create(s.validated_data)
        return Response(ret)

    @action(methods=['get'], detail=False)
    def get_detail(self, request):
        """
        refresh 是否主动刷新动态码
        """
        order_no = request.GET.get('order_no')
        # log.debug(order_no)
        # log.debug(request.META)
        try:
            order = TicketOrder.objects.get(order_no=order_no, user_id=request.user.id)
            data = TicketOrderDetailNewSerializer(order, context={'request': request}).data
        except TicketOrder.DoesNotExist:
            raise Http404
        return Response(data)

    @action(methods=['post'], detail=False)
    @atomic
    def create_order_new(self, request):
        if request.user.forbid_order:
            raise CustomAPIException('用户异常，请联系客服')
        from concu.api_limit import try_queue, get_queue_size, get_max_wait
        # todo: 测试目的,限制队列大小为1
        with try_queue('make-order', get_queue_size(), get_max_wait()) as got:
            if got:
                log.warning(f" got the queue")
                # time.sleep(10)
                log.warning(f" got the queue, and sleep over")
                source_type = self.request.data.get('source_type')
                create_serializer = ticket_order_dispatch(TicketOrder.TY_HAS_SEAT, source_type)
                s = create_serializer(data=request.data, context={'request': request})
                s.is_valid(True)
                order, prepare_order, pay_end_at, ks_order_info, xhs_order_info = s.create(s.validated_data)
                log.warning(f"got the queue and exec over")
            else:
                log.warning(f" can't the queue")
                raise CustomAPIException('手慢了，当前抢票人数较多，请稍后重试')
        return Response(data=dict(receipt_id=order.receipt.id, prepare_order=prepare_order, pay_end_at=pay_end_at,
                                  order_id=order.order_no, ks_order_info=ks_order_info, xhs_order_info=xhs_order_info))

    @action(methods=['post'], detail=False)
    @atomic
    def noseat_order_new(self, request):
        if request.user.forbid_order:
            raise CustomAPIException('用户异常，请联系客服')
        from concu.api_limit import try_queue, get_queue_size, get_max_wait
        # todo: 测试目的,限制队列大小为1
        # redis-cli
        # set app-limit-queue-size 50 并发数
        # set app-limit-max-wait 1 等待时间
        with try_queue('make-order', get_queue_size(), get_max_wait()) as got:
            if got:
                log.warning(f" got the queue")
                # time.sleep(10)
                log.warning(f" got the queue, and sleep over")
                source_type = self.request.data.get('source_type')
                create_serializer = ticket_order_dispatch(TicketOrder.TY_NO_SEAT, source_type)
                s = create_serializer(data=request.data, context={'request': request})
                s.is_valid(True)
                order, prepare_order, pay_end_at, ks_order_info, xhs_order_info = s.create(s.validated_data)
                log.warning(f"got the queue and exec over")
            else:
                log.warning(f" can't the queue")
                raise CustomAPIException('手慢了，当前抢票人数较多，请稍后重试')
        return Response(
            data=dict(receipt_id=order.receipt.id, prepare_order=prepare_order, pay_end_at=pay_end_at,
                      order_id=order.order_no, ks_order_info=ks_order_info, xhs_order_info=xhs_order_info))

    @action(methods=['post'], detail=False)
    @atomic
    def margin_order(self, request):
        s = TicketOrderMarginCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        order = s.create(s.validated_data)
        return Response(data=dict(receipt_id=order.receipt.payno, order_id=order.order_no))

    # @action(methods=['get'], detail=True)
    # def booking_order(self, request, pk):
    #     try:
    #         log.debug(pk)
    #         order = TicketOrder.objects.get(order_no=pk, user=request.user)
    #         data = TicketBooking.create_booking_new(order)
    #         return Response(data)
    #     except TicketOrder.DoesNotExist:
    #         raise CustomAPIException('找不到订单')

    @action(methods=['get'], detail=False)
    def scroll_list(self, request):
        data = TicketOrder.scroll_list()
        return Response(data)

    @action(methods=['get'], detail=True)
    def booking_order_o(self, request, pk):
        try:
            log.debug(pk)
            order = self.get_object()
            data = TicketBooking.create_booking_new(order)
            return Response(data)
        except TicketOrder.DoesNotExist:
            raise CustomAPIException('找不到订单')

    @action(methods=['get'], detail=True)
    def set_cancel(self, request, pk):
        try:
            inst = self.get_object()
        except TicketOrder.DoesNotExist:
            raise CustomAPIException('找不到订单')
        if inst.status != TicketOrder.STATUS_UNPAID:
            raise CustomAPIException('订单状态已变更，请先刷新页面！')
        ret, msg = inst.cancel()
        if ret:
            return Response(data=dict(msg=u'成功', pk=pk))
        else:
            raise CustomAPIException(msg)

    @action(methods=['get'], detail=False, permission_classes=[IsPermittedAgentUser])
    def agent_order(self, request):
        status = request.GET.get('status') or None
        qs = self.queryset.filter(agent=request.user)
        if status:
            qs = qs.filter(status=int(status))
        else:
            qs = qs.exclude(status=TicketOrder.STATUS_CANCELED)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    # @action(methods=['post'], detail=True)
    # def agent_detail(self, request, pk):
    #     try:
    #         order = TicketOrder.objects.filter(pk=pk, agent=request.user).get()
    #         return Response(TicketOrderDetailSerializer(order, context={'request': request}).data)
    #     except TicketOrder.DoesNotExist:
    #         raise CustomAPIException('找不到订单')

    # @action(methods=['get'], detail=False)
    # def code_img(self, request):
    #     code_id = request.GET.get('code_id')
    #     log.debug(code_id)
    #     if not code_id:
    #         raise CustomAPIException('参数错误')
    #     try:
    #         # inst = TicketUserCode.objects.filter(pk=int(code_id), order__user_id=request.user.id).get()
    #         inst = TicketUserCode.objects.filter(pk=int(code_id)).get()
    #         if not inst.code_img.path:
    #             raise CustomAPIException('找不到二维码')
    #         user = request.user
    #         from caches import get_redis
    #         key = 'code_img_{}_{}'.format(user.id, code_id)
    #         redis = get_redis()
    #         if redis.setnx(key, code_id):
    #             redis.expire(key, 5)
    #             import os
    #             from ticket.utils import qrcode_dir_order_codes
    #             dir, rel_url = qrcode_dir_order_codes()
    #             from common.utils import get_timestamp
    #             start_at = inst.order.session.start_at
    #             timestamp = get_timestamp(start_at)
    #             filename = 'order_code_{}_{}_v{}.png'.format(code_id, timestamp, 5)
    #             filepath = os.path.join(dir, filename)
    #             if not os.path.isfile(filepath):
    #                 from common.qrutils import order_code_img
    #                 header = '{}开演'.format(start_at.strftime('%H:%M'))
    #                 date_at = '{}'.format(start_at.strftime('%Y年%m月%d日'))
    #                 title = inst.order.title
    #                 if len(title) > 16:
    #                     title = '{}...'.format(title[:16])
    #                 seat = str(inst.session_seat) if inst.session_seat else None
    #                 code = '核销码:{}'.format(inst.code)
    #                 venue = inst.order.venue.name
    #                 if len(title) > 12:
    #                     venue = '{}...'.format(title[:12])
    #                 order_code_img(inst.code_img.path, header, date_at, title, seat, code, venue, filepath)
    #             url = request.build_absolute_uri('/'.join([rel_url, filename]))
    #             return Response(data=dict(url=url))
    #         else:
    #             raise CustomAPIException('请勿点击多次')
    #     except TicketUserCode.DoesNotExist:
    #         raise CustomAPIException('找不到核销码')

    @action(methods=['get'], detail=False)
    def code_img_new(self, request):
        code_id = request.GET.get('code_id')
        if not code_id:
            raise CustomAPIException('参数错误')
        try:
            obj = TicketUserCode.objects.get(code=code_id)
        except TicketUserCode.DoesNotExist:
            raise CustomAPIException('找不到核销码')
        if not (obj.order.user == request.user or obj.give_mobile == request.user.mobile):
            raise Http404
        can_share, deadline_at, deadline_timestamp = obj.check_can_share()
        log.debug(deadline_at)
        if not can_share:
            raise CustomAPIException('请刷新二维码后再尝试分享')
        url, code = obj.get_code_img_new()
        if not obj.code_img.path:
            raise CustomAPIException('找不到二维码')
        code_path = obj.code_img.path
        user = request.user
        from caches import get_redis
        key = 'code_img_{}_{}'.format(user.id, code_id)
        redis = get_redis()
        if redis.setnx(key, code_id):
            redis.expire(key, 5)
            import os
            from ticket.utils import qrcode_dir_order_codes
            dir, rel_url = qrcode_dir_order_codes()
            from common.utils import get_timestamp
            start_at = obj.order.session.start_at
            timestamp = get_timestamp(start_at)
            filename = '{}.png'.format(sha256_str('ordcode{}{}_v{}'.format(code, timestamp, 5)))
            filepath = os.path.join(dir, filename)
            if not os.path.isfile(filepath):
                # log.error(filepath)
                from common.qrutils import order_code_img_new
                header = '{}开演'.format(start_at.strftime('%H:%M'))
                date_at = '{}'.format(start_at.strftime('%Y年%m月%d日'))
                title = obj.order.title
                if len(title) > 16:
                    title = '{}...'.format(title[:16])
                seat = str(obj.session_seat) if obj.session_seat else None
                code_str = '核销码:{}'.format(code)
                venue = obj.order.venue.name
                if len(title) > 12:
                    venue = '{}...'.format(title[:12])
                order_code_img_new(code_path, header, date_at, title, seat, code_str, venue, filepath, deadline_at)
                obj.change_share_code_img(filepath)
            url = request.build_absolute_uri('/'.join([rel_url, filename]))
            return Response(data=dict(url=url))
        else:
            raise CustomAPIException('请勿点击多次')

    # @action(methods=['get'], detail=False, permission_classes=[])
    # def check_sign(self, request):
    #     timestamp = '1695281241'
    #     nonce_str = 'Hb8mhgiS7rjoMDm53Q2mUkbpcJcPH504'
    #     sign = 'Wso4wLHfXwq+gQfdtsJHD874xnC7+Jt3+lPYnjKYkEIcrWQntPLWmEcYStcH0PmAg++cBw1LzebO4bPCldYzxInVr7aFOMVBrofS2WFQMCizG+OTH+VRnoK6Zmp9/9ru9CInCAphBHQFE6LTSAOmb7q9rwzJWDJAttYtU3yXwoOZO9QoeiZoZxsIZThAqxig0zzqHSVh2KrtAyMyfdLAVioXJrVPl3avsrrkH1h1qZwROSXscOKJWcW7mK9DNSvQxICwKmSW5Ug4WJNY1l65NqGTXIvJZOH8Y+KtrBiyV9U45mId9Sn4vz5ktxvn23JBJ9bdDa5jvUwAvNdNt6oRKg=='
    #     data = {'version': '2.0', 'msg': '{"order_id":"ots72811774181890317381806","goods":null,"sku_list":[{"sku_id":"7280791528300103735","sku_id_type":1,"quantity":1,"origin_price":5000,"price":5000,"atts":{"code_source_type":"2","limit_rule":"{\\"is_limit\\":true,\\"total_buy_num\\":6}","settle_type":"1","use_type":"1"},"goods_info":{"img_url":"https://p6-developer-sign.bytemaimg.com/tos-cn-i-lgni0yg6nh/be61ee204dec44ada4caf70b437a0a05~tplv-ke512zj2cu-jpg.jpeg?x-expires=1850801241\\u0026x-signature=qA5fSrDBG0w36BQfujpetefvRCU%3D","title":"武汉站·李波中式单口《李姐不理解》@按座位售票","sub_title":"","labels":"","date_rule":"","poi_id":"","goods_id":"7280791528300103735","goods_id_type":1}}],"item_order_info_list":[{"goods_id":"7280791528300103735","goods_id_type":1,"sku_id":"7280791528300103735","sku_id_type":1,"item_order_id":"ots72811774181890645061806","price":5000,"coupon_item_id":"","sub_item_list":null}],"total_amount":5000,"discount":0,"cp_extra":"{\\"my_order_id\\":112}","create_order_time":1695281241545,"open_id":"_0002F9vEBO0oXEeh7XYI_wMY3oxVKyOaJFG","phone_num":"15577150426","contact_name":"凌","app_id":"tt444732fadb75092d01","union_id":"fb7fd7cf-a143-439c-b4c2-45cdc2724fc4","delivery_type":0,"biz_line":0,"fulfill_type":0}', 'type': 'pre_create_order'}
    #     from douyin import get_dou_yin
    #     dy = get_dou_yin()
    #     dd = {"eventTime": 1677653869000, "status": 102}
    #     dy.get_sign('POST', '/abc', '1680835692', 'gjjRNfQlzoDIJtVDOfUe', json.dumps(dd))
    #     dy.check_sign(http_body=json.dumps(data, ensure_ascii=False), timestamp=timestamp,
    #                   nonce_str=nonce_str, sign=sign)
    #     return Response()

    @action(methods=['post'], detail=False, permission_classes=[])
    def tiktok_notify(self, request):
        """"
        request.META
        ''REQUEST_METHOD': 'POST', HTTP_BYTE_IDENTIFYNAME': '/common/order/create_order_callback_url',
        'HTTP_BYTE_LOGID': '2023092109530364D1D7BF5BE3C7731D8A',
         'HTTP_BYTE_NONCE_STR': 'Lvd6e6w4sbxDxTIYlOwk3QAZDIXLG5du',
         'HTTP_BYTE_SIGNATURE': 'ddjdj=',
         'HTTP_BYTE_TIMESTAMP': '1695261183',
         'CONTENT_TYPE': 'application/json', 'HTTP_SIGNATURE': '2f59e5f2fa4a6c2a47c30bbd27b11095d985e35100eeffa46cf3cfc93b95de5b',
        # 预下单
        {'version': '2.0', 'msg': '{}', 'type': 'pre_create_order'}
        # 支付成功
        {'version': '2.0', 'msg': '{"app_id":"tt444732fadb75092d01","status":"SUCCESS",
        "order_id":"ots72804408227039009881806","cp_extra":"{\\"my_order_id\\":81}","message":"",
        "event_time":1695109768000,"out_order_no":"20230919154914105427","total_amount":5000,"discount_amount":0,
        "pay_channel":2,"channel_pay_id":"2023091922001428781419000406","delivery_type":0,"order_source":""}',
         'type': 'payment'}
        """
        log.debug(request.data)
        log.debug(request.META)
        data = request.data
        if data.get('type') == 'create_merchant':
            return Response({
                "err_no": 0,
                "err_tips": "success"
            })
        from douyin import get_dou_yin
        dy = get_dou_yin()
        # is_verify = True
        is_verify = dy.check_sign(http_body=json.dumps(request.data, ensure_ascii=False),
                                  timestamp=request.META['HTTP_BYTE_TIMESTAMP'],
                                  nonce_str=request.META['HTTP_BYTE_NONCE_STR'],
                                  sign=request.META['HTTP_BYTE_SIGNATURE'])
        if not is_verify:
            log.error('验签失败')
            return Response({"err_no": 9999, "err_tips": "验签错误"})
        else:
            from decimal import Decimal
            tt = request.data.get('type')
            msg = json.loads(request.data.get('msg'))
            ret = {
                "err_no": 0,
                "err_tips": "success"
            }
            if tt == 'settle':
                """
                {'version': '2.0', 'msg': '{"app_id":"tt444732fadb75092d01","status":"SUCCESS","order_id":"ots73020527038978317161476",
                "cp_extra":"","message":"SUCCESS","event_time":1701794819000,"settle_id":"7308352427978230016","out_settle_no":"7308352427978230016",
                "rake":692,"commission":0,"settle_detail":"商户号72789245768543296350-分成金额(分)19108","settle_amount":19800,"is_auto_settle":true}',
                 'type': 'settle'}
                """
                # 如果要分账的话这里需要接
                log.debug('分成回调')
                pass
                # status = msg['status']
                # order_id = msg['order_id']
                # if status == 'FAIL':
                #     order.settle_fail()
                # elif status == 'SUCCESS':
                #     order.settle_success()
            elif tt in ['pre_create_order', 'payment']:
                my_order_id = json.loads(msg['cp_extra'])['my_order_id']
                order = None
                try:
                    order = TicketOrder.objects.get(id=int(my_order_id))
                except TicketOrder.DoesNotExist:
                    log.error('找不到预下单，{}'.format(my_order_id))
                    ret['err_no'] = 1
                    ret['err_tips'] = '找不到预下单'
                if tt == 'pre_create_order':
                    tiktok_order_id = msg['order_id']
                    item_order_info_list = json.dumps(msg['item_order_info_list'])
                    actual_amount = msg['total_amount']
                    if int(order.actual_amount * 100) == actual_amount:
                        order.set_tiktok_order_id(tiktok_order_id, item_order_info_list)
                        params = {"id": order.id, "order_no": order.order_no}
                        from mp.models import BasicConfig
                        pay_expire_seconds = BasicConfig.get_pay_expire_seconds()
                        ret['data'] = {
                            "out_order_no": order.order_no,
                            "pay_expire_seconds": pay_expire_seconds,
                            "order_entry_schema": {
                                "path": tiktok_order_detail_url,
                                "params": json.dumps(params)
                            },
                            # "order_valid_time": [{
                            #     "goods_id": "xxx",
                            #     "valid_start_time": 1232312000,
                            #     "valid_end_time": 1231231000
                            # }]
                        }
                    else:
                        ret['err_no'] = 2
                        ret['err_tips'] = '订单金额错误'
                elif tt == 'payment':
                    status = msg['status']
                    if status == 'CANCEL':
                        # order.cancel()
                        pass
                    elif status == 'SUCCESS':
                        receipt = order.receipt
                        if msg['total_amount'] != int(receipt.amount * 100):
                            ret['err_no'] = 2
                            ret['err_tips'] = '订单金额错误'
                        else:
                            if msg['order_id'] == order.tiktok_order_id and order.order_no == msg[
                                'out_order_no'] and msg['total_amount'] == int(order.actual_amount * 100):
                                channel_pay_id = msg['channel_pay_id']
                                if not receipt.paid:
                                    log.debug('receipt {} transaction_id is {}'.format(receipt.id, channel_pay_id))
                                    receipt.set_paid(transaction_id=channel_pay_id)
                            else:
                                ret['err_no'] = 3
                                ret['err_tips'] = '订单ID错误'
            else:
                ret = {
                    "err_no": 1,
                    "err_tips": "类型错误"
                }
            return Response(ret)

    #
    # @action(methods=['get', 'post'], detail=False)
    # def refund_notify(self, request):
    #     """
    #     default for lp to refund notify
    #     :param request:
    #     :return:
    #     """
    #     # log.debug('refund notify {}'.format(request.META))
    #     # log.debug('refund notify data is{}'.format(request.body))
    #     from mall.pay_service import get_default_pay_client
    #     mp_pay_client = get_default_pay_client()
    #     result = mp_pay_client.parse_refund_result(request.body)
    #     log.debug('退款数据 {}'.format(result))
    #     from ticket.models import TicketOrderRefund
    #     rp = TicketOrderRefund.objects.filter(out_refund_no=result.get('out_refund_no')).first()
    #     if rp:
    #         if result.get('refund_status') == 'SUCCESS':
    #             rp.set_finished(result['total_fee'])
    #         else:
    #             rp.set_fail()
    #     else:
    #         pass
    #     xml = """<xml>
    #              <return_code><![CDATA[{}]]></return_code>
    #              <return_msg><![CDATA[{}]]></return_msg>
    #              </xml>"""
    #     from django.http import HttpResponse
    #     return HttpResponse(content=xml.format('SUCCESS', 'OK'))

    @action(methods=['get', 'post'], detail=False, permission_classes=[])
    def refund_notify(self, request):
        log.error('抖音退款回调 header {}'.format(request.META))
        log.error('抖音退款回调 data {}'.format(request.data))
        from douyin import get_dou_yin
        dy = get_dou_yin()
        # is_verify = True
        is_verify = dy.check_sign(http_body=json.dumps(request.data, ensure_ascii=False),
                                  timestamp=request.META['HTTP_BYTE_TIMESTAMP'],
                                  nonce_str=request.META['HTTP_BYTE_NONCE_STR'],
                                  sign=request.META['HTTP_BYTE_SIGNATURE'])
        if not is_verify:
            log.error('验签失败')
            return Response({"err_no": 9999, "err_tips": "验签错误"})
        else:
            from decimal import Decimal
            tt = request.data.get('type')
            msg = json.loads(request.data.get('msg'))
            ret = {
                "err_no": 0,
                "err_tips": "success"
            }
            if tt == 'refund':
                status = msg['status']
                try:
                    refund = TicketOrderRefund.objects.get(refund_id=msg['refund_id'])
                    if status == 'FAIL':
                        refund.set_fail(msg['message'])
                    elif status == 'SUCCESS':
                        if refund.status != TicketOrderRefund.STATUS_FINISHED:
                            refund.set_finished(msg['refund_total_amount'])
                except TicketOrderRefund.DoesNotExist:
                    log.error('找不到退款单，{}'.format(msg['refund_id']))
                    ret['err_no'] = 1
                    ret['err_tips'] = '找不到退款单'
            else:
                ret = {
                    "err_no": 1,
                    "err_tips": "类型错误"
                }
        log.debug(ret)
        return Response(ret)


class ShowUserViewSet(SerializerSelector, ReturnNoDetailViewSet):
    queryset = ShowUser.objects.all()
    serializer_class = ShowUserSerializer
    serializer_class_post = ShowUserCreateSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    # def list(self, request, *args, **kwargs):
    #     qs = self.queryset.filter(user=request.user)
    #     # version = request.META.get('HTTP_VERSION')
    #     # if version and version < '1.6.0' and not qs:
    #     #     from mall.models import UserAddress
    #     #     address = UserAddress.objects.filter(user_id=request.user.id).first()
    #     #     if address:
    #     #         data = {"count": 1, "next": None, "previous": None, "results": [
    #     #             {"id": 99999999, "name": address.receive_name, "mobile": address.phone, "id_card": None,
    #     #              "create_at": "2024-09-01T19:42:39.125393", "user": request.user.id}]}
    #     #         return Response(data)
    #     page = self.paginate_queryset(qs)
    #     return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    @action(methods=['get', 'post'], detail=True)
    def delete_user(self, request, pk):
        qs = self.get_object()
        if qs:
            qs.delete()
            return Response()
        else:
            raise CustomAPIException('找不到记录')


class PerformerFocusRecordViewSet(viewsets.ModelViewSet):
    queryset = PerformerFocusRecord.objects.filter(is_collect=True)
    serializer_class = PerformerFocusRecordSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)
    http_method_names = ['get']


class ShowCommentImageViewSet(SerializerSelector, ReturnNoDetailViewSet):
    queryset = ShowCommentImage.objects.none()
    serializer_class = ShowCommentImageSerializer
    serializer_class_post = ShowCommentImageCreateSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['post', 'get']


class ShowCommentViewSet(ReturnNoDetailViewSet):
    queryset = ShowComment.objects.filter(is_display=True, status=ShowComment.ST_FINISH)
    serializer_class = ShowCommentSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']
    pagination_class = StandardResultsSetPagination

    @method_decorator(cache_page(60 * 2, key_prefix=PREFIX))
    def list(self, request, *args, **kwargs):
        show_id = request.GET.get('show_id')
        if not show_id:
            raise CustomAPIException('参数错误')
        if show_id == 'undefined':
            return Response(data=[])
        qs = self.queryset.filter(show__no=show_id)
        qs_own = ShowComment.objects.filter(show__no=show_id, is_display=False, status=ShowComment.ST_FINISH,
                                            user_id=request.user.id)
        if qs_own:
            qs = qs | qs_own
        qs = qs.order_by('-is_quality', '-pk')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(
            self.serializer_class(page, many=True, context={'request': request}).data)

    @method_decorator(cache_page(60 * 5, key_prefix=PREFIX))
    @action(methods=['get'], detail=False)
    def quality(self, request):
        queryset = self.queryset.filter(is_quality=True).order_by('-pk')[:3]
        data = self.serializer_class(queryset, many=True, context={'request': request}).data
        return Response(data)


class TicketBookingViewSet(ReturnNoneViewSet):
    queryset = TicketBooking.objects.all()
    serializer_class = TicketBookingSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    # def list(self, request, *args, **kwargs):
    #     qs = self.queryset.filter(user_id=request.user.id)
    #     page = self.paginate_queryset(qs)
    #     return self.get_paginated_response(
    #         self.serializer_class(page, many=True, context={'request': request}).data)

    @action(methods=['post'], detail=False)
    def set_status(self, request):
        s = TicketBookingSetStatusSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        inst = s.create(s.validated_data)
        return Response(inst.id)


class TicketGiveRecordViewSet(DetailPKtoNoViewSet):
    queryset = TicketGiveRecord.objects.none()
    serializer_class = TicketGiveRecordSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post']
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    # def list(self, request, *args, **kwargs):
    #     qs = TicketGiveRecord.objects.filter(user_id=request.user.id)
    #     page = self.paginate_queryset(qs)
    #     return self.get_paginated_response(
    #         self.serializer_class(page, many=True, context={'request': request}).data)

    @action(methods=['get'], detail=True)
    def get_detail(self, request, pk):
        try:
            inst = TicketGiveRecord.objects.get(no=pk, give_mobile=request.user.mobile)
            data = TicketGiveRecordDetailSerializer(inst, context={'request': request}).data
            return Response(data)
        except TicketGiveRecord.DoesNotExist:
            raise CustomAPIException('找不到记录')

    @action(methods=['post'], detail=False)
    def create_record(self, request):
        s = TicketGiveRecordCreateSerializer(data=request.data, context={'request': request})
        s.is_valid(True)
        inst = s.create(s.validated_data)
        return Response(inst.no)

    @action(methods=['get'], detail=False)
    def set_cancel(self, request):
        code_id = request.GET.get('code_id')
        if not code_id:
            raise CustomAPIException('参数错误')
        from caches import get_pika_redis, give_cancel_key, give_code_key
        qs = TicketGiveDetail.objects.filter(ticket_code__code=code_id, record__user_id=request.user.id,
                                             record__status=TicketGiveRecord.STAT_DEFAULT)
        if qs:
            inst = qs.first()
            cancel_key = give_cancel_key.format(inst.id)
            key = give_code_key.format(inst.id)
            with get_pika_redis() as redis:
                if redis.setnx(key, 1):
                    redis.expire(key, 3)
                    if redis.setnx(cancel_key, 1):
                        redis.expire(cancel_key, 3)
                        inst.record.set_cancel()
                    else:
                        raise CustomAPIException('请勿重复取消')
                else:
                    raise CustomAPIException('取消失败，领取人正在领取')
            return Response()
        else:
            raise CustomAPIException('取消失败，未找到满足条件的记录')

    @action(methods=['get'], detail=True)
    def set_receive(self, request, pk):
        try:
            from caches import get_pika_redis, give_code_key, give_cancel_key
            key = give_code_key.format(pk)
            cancel_key = give_cancel_key.format(pk)
            with get_pika_redis() as redis:
                if redis.setnx(cancel_key, 1):
                    redis.expire(cancel_key, 3)
                    if redis.setnx(key, 1):
                        redis.expire(key, 3)
                        inst = TicketGiveRecord.objects.get(no=pk, give_mobile=request.user.mobile,
                                                            status=TicketGiveRecord.STAT_DEFAULT)
                        inst.set_receive(request.user)
                        return Response()
                    else:
                        raise CustomAPIException('请勿重复领取')
                else:
                    raise CustomAPIException('赠送人已取消领取')
        except TicketGiveRecord.DoesNotExist:
            raise CustomAPIException('请使用正确的手机号领取，如有疑问请联系赠送人')
