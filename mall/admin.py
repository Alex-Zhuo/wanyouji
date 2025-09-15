# coding: utf-8

import xlwt
from django.contrib import admin
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone

import logging
from django.core.exceptions import PermissionDenied
from dj_ext.permissions import RemoveDeleteModelAdmin, OnlyViewAdmin, ChangeAndViewAdmin, \
    OnlyReadTabularInline
from django.utils.safestring import mark_safe
from dj_ext.exceptions import AdminException
from restframework_ext.filterbackends import UserAdminTypeFilter

log = logging.getLogger(__name__)
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from mall.models import Receipt, User, HotSearch, MembershipCard, MembershipImage, CardRecord, MemberCardRecord, \
    AgreementRecord, TheaterCardTicketLevel, \
    TheaterCardCity, TheaterCardImage, TheaterCard, TheaterCardUserBuy, TheaterCardUserRecord, TheaterCardOrder, \
    TheaterCardChangeRecord, UserAddress, TheaterCardChangeRecordDetail, TheaterCardUserDetail
from dj_ext.filters import HasParentFilter
from django.utils.translation import ugettext_lazy as _
from dj import technology_admin
from datetime import datetime


def set_member(modeladmin, request, queryset):
    mc = MembershipCard.get()
    for user in queryset.all():
        inst = MemberCardRecord.create_record(user, Receipt.PAY_NOT_SET, mc, MemberCardRecord.ST_ADMIN)
        inst.set_paid()
    messages.success(request, '执行成功')


set_member.short_description = '设置为会员'


class LargeTablePaginator(Paginator):
    def _get_count(self):
        return 30000000

    count = property(_get_count)


class UserAdmin(BaseUserAdmin, RemoveDeleteModelAdmin):
    # paginator = LargeTablePaginator
    show_full_result_count = False
    ordering = ['-pk']
    autocomplete_fields = ['parent']
    search_fields = ['=mobile', '=id']
    list_filter = (UserAdminTypeFilter, 'date_joined', 'follow', HasParentFilter, 'is_active', 'is_staff')
    # actions = [set_member]
    nonsuperuser_readonly_fields = ['username', 'parent', 'new_parent_cache', 'new_parent_at_cache']
    # has_delete 用于是否有删除权限
    readonly_fields = ['new_parent_cache', 'new_parent_at_cache']
    list_display = (
        'id', 'username', 'mobile', 'last_name', 'first_name',
        'parent', 'new_parent_cache', 'new_parent_at_cache', 'is_active', 'flag', 'agree_member',
        'agree_privacy', 'agree_agent', 'date_joined', 'share_code', 'follow', 'unionid', 'lp_openid', 'openid',
        'unionid_tiktok',
        'openid_tiktok')
    non_superuser_list_display = ('username', 'first_name')
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'password1', 'password2', 'mobile', 'parent', 'parent_at', 'is_staff', 'groups'),
        }),
    )
    superuser_changeform_fieldsets = (
        (None,
         {'fields': ('username', 'password', 'last_name', 'first_name', 'mobile', 'flag')}),
        (_('Permissions'), {'fields': ('agree_member',
                                       'agree_privacy', 'agree_agent', 'is_active', 'is_staff', 'is_superuser',
                                       'groups')}),
        (_('上级'), {'fields': ('parent', 'parent_at', 'new_parent_cache', 'new_parent_at_cache')}),
    )
    # 技术人员账号不能修改密码
    tg_changeform_fieldsets = (
        (None,
         {'fields': ('username', 'last_name', 'first_name', 'mobile', 'flag')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        (_('上级'), {'fields': ('parent', 'parent_at', 'new_parent_cache', 'new_parent_at_cache')}),
    )

    nonsuperuser_changeform_fieldsets = (
        (None,
         {'fields': ('password', 'first_name', 'last_name', 'mobile', 'parent', 'parent_at', 'new_parent_cache',
                     'new_parent_at_cache')}),
    )

    nonsuperuser_changable_fields = (
        'password', 'first_name', 'last_name', 'mobile', 'parent', 'parent_at', 'new_parent_cache',
        'new_parent_at_cache'
    )
    list_per_page = 100

    def get_search_results(self, request, queryset, search_term):
        o_qs = queryset.filter(is_active=True)
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        search_type = request.GET.get('useradmin_type__exact')
        if search_term:
            if not search_type:
                raise AdminException('请选择搜索类型再搜索')
            search_type = int(search_type)
            if search_type == 1:
                queryset = o_qs.filter(id=int(search_term))
            elif search_type == 2:
                queryset = o_qs.filter(mobile=search_term)
            elif search_type == 3:
                queryset = o_qs.filter(username=search_term)
            elif search_type == 4:
                queryset = o_qs.filter(share_code=search_term)
        return queryset, use_distinct

    # date_hierarchy = 'date_joined'
    def parent_display_name(self, obj):
        return obj.parent.get_full_name() if obj.parent else None

    parent_display_name.short_description = '上级用户'

    def new_parent_cache(self, obj):
        from mall.user_cache import get_user_new_parent
        new_parent = get_user_new_parent(obj.id)
        return new_parent['name'] if new_parent else ''

    new_parent_cache.short_description = '最新推荐人'

    def new_parent_at_cache(self, obj):
        from mall.user_cache import get_user_new_parent
        new_parent = get_user_new_parent(obj.id)
        return datetime.fromtimestamp(new_parent['date_at_timestamp']).strftime(
            '%Y-%m-%d %H:%M') if new_parent and new_parent['date_at_timestamp'] else ''

    new_parent_at_cache.short_description = '被推荐时间'

    def parent_rule(self, obj):
        desc = '<上级用户>每3个月可以换绑一次，<最新推荐人>每次扫码不是同一推荐人都会换绑'
        return desc

    parent_rule.short_description = '规则'

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_readonly_fields(request, obj)
        else:
            return self.nonsuperuser_readonly_fields

    def get_fieldsets(self, request, obj=None):
        if not obj:
            # add
            return self.add_fieldsets
        # change
        if request.user.is_superuser:
            if obj.is_tg:
                return self.tg_changeform_fieldsets
            else:
                return self.superuser_changeform_fieldsets
        else:
            return self.nonsuperuser_changeform_fieldsets

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not request.user == obj:
            raise PermissionDenied()
        if not request.user.is_superuser:
            if set(form.changed_data).difference(set(self.nonsuperuser_changable_fields)):
                raise PermissionDenied()
        if not change:
            # same as super implement
            obj.save()
        else:
            # generate signal
            if 'groups' in form.changed_data:
                form.changed_data.remove('groups')
            obj.save(update_fields=form.changed_data)

    # def get_queryset(self, request):
    #     from django.core.paginator import Paginator
    #     queryset = super().get_queryset(request)
    #     paginator = Paginator(queryset, self.list_per_page)
    #     page_number = request.GET.get('page')
    #     page_obj = paginator.get_page(page_number)
    #     return page_obj


def _write_row_by_xlwt(ws, cells, row_index):
    """
    :param ws:
    :param cells: cell values
    :param row_index: 1-relative row index
    :return:
    """
    for col, cell in enumerate(cells, 0):
        ws.write(row_index - 1, col, cell)


class HotSearchAdmin(admin.ModelAdmin):
    pass


class MembershipImageInline(admin.StackedInline):
    model = MembershipImage
    extra = 0


class MembershipCardAdmin(RemoveDeleteModelAdmin):
    inlines = [MembershipImageInline]

    def changelist_view(self, request, extra_context=None):
        obj = MembershipCard.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class MemberCardRecordInline(admin.TabularInline):
    model = MemberCardRecord
    extra = 0
    readonly_fields = ['transaction_id']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(status=MemberCardRecord.STATUS_PAID)

    def transaction_id(self, obj):
        return obj.receipt.transaction_id if obj.receipt else ''

    transaction_id.short_description = '微信(抖音)支付单号'

    def has_add_permission(self, request, obj):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CardRecordAdmin(ChangeAndViewAdmin):
    list_display = ['user', 'mobile', 'source_type', 'deadline_at']
    list_filter = ['deadline_at']
    search_fields = ['=user__mobile', 'user__last_name']
    inlines = [MemberCardRecordInline]
    autocomplete_fields = ['user']
    readonly_fields = ['user', 'mobile', 'source_type']
    list_per_page = 50

    def source_type(self, obj):
        mc = MemberCardRecord.objects.filter(card=obj).first()
        return mc.get_source_type_display() if mc else None

    source_type.short_description = '授权类型'

    def mobile(self, obj):
        return obj.user.mobile

    mobile.short_description = '手机号'


class MemberCardRecordAdmin(OnlyViewAdmin):
    list_display = ['payno', 'transaction_id', 'user', 'mobile', 'card_agent', 'amount', 'status', 'pay_type']
    search_fields = ['=transaction_id', '=order_no', '=mobile']
    list_filter = ['status', 'pay_type']
    readonly_fields = ['card', 'card_agent', 'mobile', 'receipt']

    def has_add_permission(self, request):
        return False

    # def has_delete_permission(self, request, obj=None):
    #     return False

    def payno(self, obj):
        return obj.receipt.payno if obj.receipt else None

    payno.short_description = '商户订单号'


class AgreementRecordAdmin(OnlyViewAdmin):
    list_display = ['user', 'agree_member', 'agree_privacy', 'create_at']
    list_filter = ['create_at']


class TheaterCardTicketLevelInline(admin.StackedInline):
    model = TheaterCardTicketLevel
    extra = 0


class TheaterCardCityInline(admin.StackedInline):
    model = TheaterCardCity
    extra = 0
    autocomplete_fields = ['cities']


class TheaterCardImageInline(admin.StackedInline):
    model = TheaterCardImage
    extra = 0


class TheaterCardAdmin(RemoveDeleteModelAdmin):
    list_display = ['title', 'amount', 'receive_amount', 'day_max_num', 'customer_mobile', 'customer_mobile_s',
                    'is_open', 'create_at']
    search_fields = ['title']
    list_filter = ['is_open']
    inlines = [TheaterCardTicketLevelInline, TheaterCardCityInline, TheaterCardImageInline]


class TheaterCardUserBuyInline(OnlyReadTabularInline):
    model = TheaterCardUserBuy
    extra = 0


class TheaterCardUserDetailInline(admin.TabularInline):
    model = TheaterCardUserDetail
    extra = 0
    autocomplete_fields = ['user_card', 'card']


class TheaterCardUserRecordAdmin(ChangeAndViewAdmin):
    list_display = ['card_no', 'user', 'mobile', 'amount', 'today_buy_num', 'discount_total', 'venue', 'agent',
                    'create_at']
    list_filter = ['create_at']
    search_fields = ['=card_no', '=user__mobile', 'venue__name', 'user__last_name']
    inlines = [TheaterCardUserDetailInline, TheaterCardUserBuyInline]
    # autocomplete_fields = ['user']
    readonly_fields = ['user', 'agent', 'venue', 'mobile', 'card_no']
    list_per_page = 50

    def mobile(self, obj):
        return obj.user.mobile

    mobile.short_description = '手机号'

    def today_buy_num(self, obj):
        tc = TheaterCardUserBuy.get_inst(obj)
        return tc.num if tc else 0

    today_buy_num.short_description = '今日已购票数'


def set_card_paid(modeladmin, request, queryset):
    for order in queryset.filter(status=TheaterCardOrder.STATUS_UNPAID):
        order.set_paid()
    messages.success(request, '操作成功')


set_card_paid.short_description = '后台付款'


def export_theater_card_order(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')

    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('剧场会员卡订单',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('数据')
    row_index = 1
    _write_row_by_xlwt(ws,
                       [u'商户订单号', u'微信(抖音)支付单号', u'剧场会员卡', u'用户', u'手机号', u'用户剧场会员卡号',
                        u'演出场馆（门店）', u'推荐人(代理)', '实付金额', '状态'],
                       row_index)
    row_index += 1
    for record in queryset:
        data = [record.receipt.payno if record.receipt else None,
                record.receipt.transaction_id if record.receipt else None, str(record.card) if record.card else '',
                str(record.user),
                record.user.mobile, record.card_no, str(record.venue) if record.venue else '',
                str(record.agent) if record.agent else '',
                record.amount, record.get_status_display()]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


export_theater_card_order.short_description = '导出选中记录'


class TheaterCardOrderAdmin(OnlyViewAdmin):
    list_display = ['id', 'payno', 'transaction_id', 'card', 'user', 'mobile', 'card_no', 'venue', 'agent', 'amount',
                    'status']
    search_fields = ['=transaction_id', '=mobile', '=card_no']
    list_filter = ['status', 'venue', 'pay_at']
    readonly_fields = ['user', 'mobile', 'agent', 'card', 'venue', 'receipt']
    actions = [export_theater_card_order, set_card_paid]

    # def get_queryset(self, request):
    #     qs = super().get_queryset(request)
    #     return qs.filter(status=TheaterCardOrder.STATUS_PAID)

    # def mobile(self, obj):
    #     return obj.user.mobile
    #
    # mobile.short_description = '手机号'

    def payno(self, obj):
        return obj.receipt.payno if obj.receipt else None

    payno.short_description = '商户订单号'

    # def transaction_id(self, obj):
    #     return obj.receipt.transaction_id if obj.receipt else None
    #
    # transaction_id.short_description = '微信(抖音)支付单号'


def export_theater_card_change(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')

    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('剧场会员卡订单',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('数据')
    row_index = 1
    _write_row_by_xlwt(ws,
                       [u'用户', u'数额', u'结算后卡余额', '扣款明细', u'类型', u'票务订单', u'演出场次', u'剧场会员卡订单号', u'创建时间'],
                       row_index)
    row_index += 1
    for record in queryset:
        create_at = record.create_at.strftime('%Y-%m-%d %H:%M:%S')
        qs = TheaterCardChangeRecordDetail.objects.filter(record=record)
        detail = ''
        for tcd in qs:
            if detail:
                detail += '，'
            detail += '{}：{}'.format(str(tcd.card_detail), tcd.amount)
        data = [str(record.user), record.amount, record.after_amount, detail, record.get_source_type_display(),
                str(record.ticket_order) if record.ticket_order else '',
                str(record.ticket_order.session) if record.ticket_order else '',
                record.card_order_no, create_at]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


export_theater_card_change.short_description = '导出选中记录'


class TheaterCardChangeRecordDetailInline(OnlyReadTabularInline):
    model = TheaterCardChangeRecordDetail
    extra = 0
    readonly_fields = ['card']

    def card(self, obj):
        return str(obj.card_detail.card)

    card.short_description = '剧场会员卡'


class TheaterCardChangeRecordAdmin(OnlyViewAdmin):
    list_display = ['user', 'amount', 'after_amount', 'detail', 'source_type', 'ticket_order', 'session',
                    'card_order_no', 'create_at']
    list_filter = ['create_at', 'source_type']
    search_fields = ['user__last_name', '=user__mobile', '=ticket_order__order_no']
    autocomplete_fields = ['user', 'ticket_order']
    actions = [export_theater_card_change]
    inlines = [TheaterCardChangeRecordDetailInline]

    def session(self, obj):
        return str(obj.ticket_order.session) if obj.ticket_order else None

    session.short_description = '演出场次'

    def detail(self, obj):
        qs = TheaterCardChangeRecordDetail.objects.filter(record=obj)
        html = ''
        for inst in qs:
            html += '<p>{}：{}</p>'.format(str(inst.card_detail), inst.amount)
        return mark_safe(html) if qs else None

    detail.short_description = '扣款明细'


class UserAddressAdmin(RemoveDeleteModelAdmin):
    list_display = ['user', 'province', 'city', 'county', 'address', 'receive_name', 'phone']
    search_fields = ['=phone', '=receive_name']
    actions = ['export_address']

    def export_address(modeladmin, request, queryset):
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('用户地址数据',
                                                                                    timezone.now().strftime(
                                                                                        '%Y%m%d%H%M%S'))
        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('用户地址数据')
        row_index = 1
        _write_row_by_xlwt(ws, [u'用户名', u'省', u'市', u'区/县', u'收货地址', u'电话号码', u'收货人姓名'], row_index)
        row_index += 1
        for record in queryset:
            username = record.user.last_name or record.user.username
            data = [username, record.province, record.city, record.county, record.address, record.phone,
                    record.receive_name]
            _write_row_by_xlwt(ws, data, row_index)
            row_index += 1
        _write_row_by_xlwt(ws, ['END'], row_index)
        wb.save(response)
        return response

    export_address.short_description = u'导出用户地址数据'


admin.site.register(User, UserAdmin)
admin.site.register(AgreementRecord, AgreementRecordAdmin)
admin.site.register(HotSearch, HotSearchAdmin)
admin.site.register(UserAddress, UserAddressAdmin)
# admin.site.register(MembershipCard, MembershipCardAdmin)
# admin.site.register(CardRecord, CardRecordAdmin)
# admin.site.register(MemberCardRecord, MemberCardRecordAdmin)
# admin.site.register(TheaterCard, TheaterCardAdmin)
# admin.site.register(TheaterCardUserRecord, TheaterCardUserRecordAdmin)
# admin.site.register(TheaterCardOrder, TheaterCardOrderAdmin)
# admin.site.register(TheaterCardChangeRecord, TheaterCardChangeRecordAdmin)

technology_admin.register(User, UserAdmin)
technology_admin.register(AgreementRecord, AgreementRecordAdmin)
technology_admin.register(HotSearch, HotSearchAdmin)
technology_admin.register(UserAddress, UserAddressAdmin)
# technology_admin.register(MembershipCard, MembershipCardAdmin)
# technology_admin.register(CardRecord, CardRecordAdmin)
# technology_admin.register(MemberCardRecord, MemberCardRecordAdmin)
# technology_admin.register(TheaterCard, TheaterCardAdmin)
# technology_admin.register(TheaterCardUserRecord, TheaterCardUserRecordAdmin)
# technology_admin.register(TheaterCardOrder, TheaterCardOrderAdmin)
# technology_admin.register(TheaterCardChangeRecord, TheaterCardChangeRecordAdmin)
