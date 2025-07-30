# coding: utf-8
import logging
import os

from django.db import models
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from django.utils import timezone
from django.db.models import Sum
# Create your views here.
from common.config import get_config
from common.qrutils import gen_wxa_invite_code
from home.views import ReturnNoDetailViewSet, ReturnNoneViewSet
from mp.models import ShareQrcodeBackground
from mall.utils import qrcode_dir_pro
from mp.wechat_client import get_wxa_client
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.filterbackends import OwnerFilterMixinDjangoFilterBackend
from restframework_ext.mixins import SerializerSelector
from restframework_ext.pagination import DefaultNoPagePagination, StandardResultsSetPagination
from shopping_points.serializers import UserAccountLevelSerializer, \
    TransferBalanceRecordSerializer, TransferBalanceRecordDetailSerializer, \
    UserBalanceTransferCreateSerializer, ServiceConfigSerializer, UserCommissionMonthRecordSerializer, \
    UserCommissionMonthRecordRankSerializer
from shopping_points.serializers import CommissionWithdrawSerializer
from shopping_points.serializers import PointWithdrawSerializer
from restframework_ext.permissions import IsPermittedUser, IsPermittedCommissionMonthUser
from dj_ext.filters import OwnerFilterBackend
from shopping_points.models import TransferBalanceRecord, UserCommissionMonthRecord
from mp.models import ServiceConfig
from shopping_points.models import UserAccountLevel
from shopping_points.models import CommissionWithdraw
from shopping_points.models import PointWithdraw
from shopping_points.models import UserAccount
from shopping_points.models import UserCommissionChangeRecord
from shopping_points.models import UserPointChangeRecord
from shopping_points.models import ReceiptAccount
from shopping_points.serializers import UserAccountSerializer
from shopping_points.serializers import UserCommissionChangeRecordSerializer
from shopping_points.serializers import UserPointChangeRecordSerializer
from shopping_points.serializers import ReceiptAccountSerializer
from django.core.cache import cache

logger = logging.getLogger(__name__)


class UserAccountLevelViewSet(ReturnNoDetailViewSet):
    queryset = UserAccountLevel.objects.all()
    serializer_class = UserAccountLevelSerializer
    permission_classes = [IsPermittedUser]
    http_method_names = ['get']

    @action(methods=['get'], detail=False)
    def get_approve_level(self, request):
        level = request.user.account.level
        qs = self.queryset.filter(is_agent=True)
        if level:
            qs = qs.filter(grade__gt=level.grade)
        return Response(self.serializer_class(qs, many=True, context={'request': request}).data)


class WithdrawViewSetMixin(object):

    @action(methods=['get'], detail=False)
    def rules(self, request):
        from mp.models import BasicConfig
        bc = BasicConfig.get()
        data = dict(withdraw_fees_ratio=bc.withdraw_fees_ratio, withdraw_fees_min=bc.withdraw_min)
        return Response(data)


class CommissionWithdrawViewSet(WithdrawViewSetMixin, ModelViewSet):
    serializer_class = CommissionWithdrawSerializer
    queryset = CommissionWithdraw.objects.all()
    permission_classes = [IsPermittedUser]
    filter_backends = [OwnerFilterBackend.new('account__user')]
    pagination_class = DefaultNoPagePagination

    @action(methods=['get'], detail=False)
    def can_withdraw(self, request):
        """
        根据用户希望提现的金额，计算出实际到账金额、手续费、合计扣除
        :param request:
        :return:
        """
        user = request.user
        # amount = user.account.commission_balance
        amount = request.GET.get('amount')
        useraccount = user.user_account
        total, actual, fee = useraccount.can_withdraw(amount)
        return Response(data=dict(total=total, actual=actual, fee=fee))


class PointWithdrawViewSet(WithdrawViewSetMixin, ReturnNoneViewSet):
    serializer_class = PointWithdrawSerializer
    queryset = PointWithdraw.objects.all()
    permission_classes = [IsPermittedUser]
    filter_backends = [OwnerFilterBackend.new('account__user')]


class UserAccountViewSet(ReadOnlyModelViewSet, ReturnNoneViewSet):
    permission_classes = [IsPermittedUser]
    serializer_class = UserAccountSerializer
    queryset = UserAccount.objects.all()
    filter_backends = (OwnerFilterMixinDjangoFilterBackend,)

    @action(methods=['get'], detail=False)
    def info(self, request):
        from caches import account_info_cache_key
        key = account_info_cache_key.format(request.user.id)
        # 获取缓存数据
        data = cache.get(key)
        if not data:
            data = self.get_serializer(request.user.account).data
            cache.set(key, data, timeout=60)
        return Response(data)

    @action(methods=['get'], detail=False)
    def month_commission_balance(self, request):
        year = timezone.now().year
        month = timezone.now().month
        last_month, last_year = (month - 1, year) if month - 1 > 0 else (12, year - 1)
        uc = UserCommissionMonthRecord.objects.filter(account=request.user.account, year=year, month=month).first()
        data = dict(last_month=0, month=0)
        data['month'] = uc.amount if uc else 0
        uc = UserCommissionMonthRecord.objects.filter(account=request.user.account, year=last_year,
                                                      month=last_month).first()
        data['last_month'] = uc.amount if uc else 0
        return Response(data)

    # @action(methods=['post'], detail=False)
    # def transfer(self, request):
    #     """
    #     转增余额
    #     :param request:
    #     :return:
    #     """
    #     s = UserBalanceTransferCreateSerializer(data=request.data, context=dict(request=request))
    #     if s.is_valid(True):
    #         s.save()
    #     return Response()

    # @action(methods=['get'], detail=False)
    # def invite_levels(self, request):
    #     level = request.user.user_account.level
    #     max_grade = UserAccountLevel.objects.order_by('-grade').values_list('grade', flat=True).first()
    #     if level:
    #         # pages/apply/main
    #         return Response(UserAccountLevelSummarySerializer(
    #             instance=UserAccountLevel.objects.filter(grade__lt=min(max_grade, level.grade + 1)), many=True).data)
    #     else:
    #         return Response()

    @action(methods=['get'], detail=False)
    def invite_wxa_code(self, request):
        """
        邀请代理的小程序码
        :param request:
        :return:
        """
        user = request.user
        scene = 'inv_%s' % user.share_code
        #
        dir, rel_url = qrcode_dir_pro()
        sqbg = ShareQrcodeBackground.get()
        filename = 'inv_%s_v%s.png' % (user.share_code, sqbg.ver if sqbg else 0)
        filepath = os.path.join(dir, filename)
        if not os.path.isfile(filepath):
            wxa = get_wxa_client()
            buf = wxa.biz_get_wxa_code_unlimited(scene, get_config()['base']['wxa_share_url'])
            if buf:
                gen_wxa_invite_code(buf, filepath, user.last_name, user.avatar, user.id,
                                    sqbg.image.path if sqbg else None)
        url = request.build_absolute_uri('/'.join([rel_url, filename]))
        return Response(data=dict(url=url))


class UserCommissionChangeRecordViewSet(ReadOnlyModelViewSet, ReturnNoDetailViewSet):
    permission_classes = [IsPermittedUser]
    serializer_class = UserCommissionChangeRecordSerializer
    queryset = UserCommissionChangeRecord.objects.all()
    filter_backends = [OwnerFilterBackend.new('account__user')]
    filter_fields = ('status', 'source_type')
    pagination_class = DefaultNoPagePagination

    @action(methods=['get'], detail=False)
    def user_type_list(self, request):
        type = request.GET.get('type') or 0
        type = int(type)
        qs = UserCommissionChangeRecord.objects.filter(account=request.user.account, source_type=type)
        total = qs.aggregate(total=Sum('amount'))['total']
        ret = dict(total=total)
        if not request.GET.get('page_size'):
            ret['data'] = self.get_serializer(qs, many=True).data
            return Response(ret)
        else:
            page = self.paginate_queryset(qs)
            ret['data'] = self.serializer_class(page, many=True, context={'request': request}).data
            return self.get_paginated_response(ret)

    @action(methods=['get'], detail=False)
    def usercommission_type(self, request):
        source_type_choices = dict(UserCommissionChangeRecord.SOURCE_TYPE_CHOICES)
        return Response(source_type_choices)

    @action(methods=['get'], detail=False)
    def get_share_record(self, request):
        queryset = self.queryset.filter(account=request.user.account,
                                        source_type=UserCommissionChangeRecord.SOURCE_TYPE_SHARE_AWARD)
        if not request.GET.get('page_size'):
            data = self.serializer_class(queryset, many=True, context={'request': request}).data
            return Response(data)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    # @action(methods=['get'], detail=False)
    # def get_approve_record(self, request):
    #     queryset = self.queryset.filter(approve_account=request.user.account,
    #                                     source_type=UserCommissionChangeRecord.SOURCE_TYPE_SHARE_AWARD)
    #     if not request.GET.get('page_size'):
    #         data = self.serializer_class(queryset, many=True, context={'request': request}).data
    #         return Response(data)
    #     page = self.paginate_queryset(queryset)
    #     return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)

    # @action(methods=['post'], detail=True)
    # def approve(self, request, pk):
    #     obj = UserCommissionChangeRecord.objects.filter(pk=pk, status=UserCommissionChangeRecord.STATUS_UNSETTLE,
    #                                                     approve_account=request.user.account).first()
    #     if obj:
    #         obj.settle()
    #     else:
    #         raise CustomAPIException('发放奖励状态错误')
    #     return Response()

    @action(methods=['get'], detail=False)
    def stat(self, request):
        res = dict()
        now = timezone.now()
        res['share_award_today'] = UserCommissionChangeRecord.objects.filter(
            create_at__year=now.year, create_at__month=now.month,
            create_at__day=now.day, account=request.user.user_account,
            source_type__in=UserCommissionChangeRecord.record_to_balance_source_types()).exclude(
            status__in=(UserCommissionChangeRecord.STATUS_INVALID,)).aggregate(sum=Sum('amount'))['sum'] or 0
        res['share_award_this_month'] = UserCommissionChangeRecord.objects.filter(
            create_at__year=now.year, create_at__month=now.month,
            account=request.user.user_account,
            source_type__in=UserCommissionChangeRecord.record_to_balance_source_types()).exclude(
            status__in=(UserCommissionChangeRecord.STATUS_INVALID,)).aggregate(sum=Sum('amount'))['sum'] or 0
        res['share_award_total'] = UserCommissionChangeRecord.objects.filter(
            account=request.user.user_account,
            source_type__in=UserCommissionChangeRecord.record_to_balance_source_types()).exclude(
            status__in=(UserCommissionChangeRecord.STATUS_INVALID,)).aggregate(sum=Sum('amount'))['sum'] or 0
        return Response(res)


class UserCommissionMonthRecordViewSet(ReadOnlyModelViewSet, ReturnNoDetailViewSet):
    permission_classes = [IsPermittedCommissionMonthUser]
    serializer_class = UserCommissionMonthRecordSerializer
    queryset = UserCommissionMonthRecord.objects.all()
    pagination_class = StandardResultsSetPagination

    def list(self, request, *args, **kwargs):
        year = timezone.now().year
        month = timezone.now().month
        qs = self.queryset.filter(year=year, month=month)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.serializer_class(page, many=True, context={'request': request}).data)
    @action(methods=['get'], detail=False)
    def ranking_list(self, request):
        year = timezone.now().year
        month = timezone.now().month
        qs = self.queryset.filter(year=year, month=month)
        data = UserCommissionMonthRecordRankSerializer(qs, many=True, context={'request': request}).data
        return Response(data)

    # @action(methods=['get'], detail=False)
    # def ranking_list(self, request):
    #     year = timezone.now().year
    #     month = timezone.now().month
    #     qs = self.queryset.filter(year=year, month=month)
    #     ty = request.GET.get('ty') or None
    #     data = []
    #     if ty:
    #         ty = int(ty)
    #         from ticket.models import ShowType
    #         xunyan = ShowType.xunyan()
    #         dkxj = ShowType.dkxj()
    #         # tkx = ShowType.tkx()
    #         if ty == 1:
    #             qs = qs.filter(show_type=xunyan)
    #             data = UserCommissionMonthRecordRankSerializer(qs, many=True, context={'request': request}).data
    #         elif ty == 2:
    #             qs = qs.filter(show_type_id=dkxj.id).values('account_id').order_by('account_id').annotate(
    #                 total=Sum('amount')).order_by('-total')[:10]
    #         else:
    #             qs = qs.none()
    #     else:
    #         qs = qs.values('account_id').order_by('account_id').annotate(total=Sum('amount')).order_by('-total')[:10]
    #     if qs and not data:
    #         for dd in list(qs):
    #             account = UserAccount.objects.get(id=dd['account_id'])
    #             user = account.user
    #             if user.icon:
    #                 avatar = request.build_absolute_uri(user.icon.url)
    #             else:
    #                 avatar = user.avatar
    #             data.append(dict(amount=dd['total'], user_info=dict(name=user.get_full_name(), avatar=avatar)))
    #     return Response(data)


class UserPointChangeRecordViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsPermittedUser]
    serializer_class = UserPointChangeRecordSerializer
    queryset = UserPointChangeRecord.objects.all().order_by('-create_at')
    filter_backends = [OwnerFilterBackend.new('account__user')]
    filter_fields = ('status', 'source_type')
    pagination_class = StandardResultsSetPagination


class ReceiptAccountViewSet(ModelViewSet):
    queryset = ReceiptAccount.objects.all()
    serializer_class = ReceiptAccountSerializer
    permission_classes = [IsPermittedUser]
    filter_backends = [OwnerFilterBackend.new('account__user')]


class TransferBalanceRecordViewSet(SerializerSelector, viewsets.ModelViewSet):
    queryset = TransferBalanceRecord.objects.all()
    serializer_class = TransferBalanceRecordSerializer
    serializer_class_retrieve = TransferBalanceRecordDetailSerializer
    permission_classes = [IsPermittedUser]
    pagination_class = DefaultNoPagePagination
    http_method_names = ['get', 'post']

    def get_queryset(self):
        qs = super(TransferBalanceRecordViewSet, self).get_queryset()
        user = self.request.user
        return qs.filter(models.Q(source__user=user) | models.Q(to__user=user))

    def update(self, request, *args, **kwargs):
        return Response(status=400)

    @action(methods=['put'], detail=True)
    def confirm(self, request, pk):
        """
        确认转赠。仅是修改状态
        :param request:
        :param pk:
        :return:
        """
        o = self.get_object()
        if o.to and o.to.user == self.request.user:
            o.confirm()
            return Response()
        else:
            return Response(status=403)


class ServiceConfigViewSet(ReturnNoDetailViewSet):
    serializer_class = ServiceConfigSerializer
    queryset = ServiceConfig.objects.all()
    pagination_class = DefaultNoPagePagination
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        inst = ServiceConfig.get()
        return Response(self.serializer_class(inst).data)
