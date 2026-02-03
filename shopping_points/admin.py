# coding: utf-8

import xlwt
from django.contrib import admin
from django.http import HttpResponse
from wechatpy.exceptions import WeChatPayException
from django.utils import timezone

from dj_ext.permissions import RemoveDeleteModelAdmin, OnlyViewAdmin, ChangeAndViewAdmin
from restframework_ext.filterbackends import YearFilter, MonthFilter, CardShowTypeFilter
from .models import UserCommissionMonthRecord
from .models import UserAccountLevel
from .models import UserAccount
from .models import UserCommissionChangeRecord
from .models import CommissionWithdraw
from django.contrib import messages
from dj import technology_admin


class UserPointChangeRecordAdmin(RemoveDeleteModelAdmin):
    calc_field = 'amount'
    list_display = ['id', 'account', 'amount', 'source_type', 'status', 'create_at', 'desc', 'order']
    list_filter = ['source_type', 'status']
    search_fields = ['order__id', 'account__user__last_name', 'account__user__username', 'order__orderno']


def export_usercommission(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')

    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('佣金明细',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('数据')
    row_index = 1
    _write_row_by_xlwt(ws,
                       [u'用户', u'状态', u'下单人昵称', u'下单人手机号', u'金额', u'节目分类', u'类型', u'创建时间', u'描述'],
                       row_index)
    row_index += 1
    for record in queryset:
        create_at = record.create_at.strftime('%Y-%m-%d %H:%M:%S')
        nickname = ''
        mobile = ''
        if record.order:
            nickname = record.order.user.last_name
            mobile = record.order.user.mobile
        elif record.card_order:
            nickname = record.card_order.card.user.last_name
            mobile = record.card_order.user.mobile
        elif record.theater_order:
            nickname = record.theater_order.user.last_name
            mobile = record.theater_order.user.mobile
        data = [str(record.account), record.get_status_display(), nickname, mobile, record.amount,
                str(record.show_type) if record.show_type else '',
                record.get_source_type_display(), create_at, record.desc]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


export_usercommission.short_description = '导出记录'


def set_invalid(modeladmin, request, queryset):
    queryset = queryset.filter(status=UserCommissionChangeRecord.STATUS_CAN_WITHDRAW)
    for inst in queryset:
        inst.account.update_commission_balance(-inst.amount, show_type=inst.show_type)
        if inst.order:
            inst.order.change_agent_c_amount(-inst.amount)
        inst.status = UserCommissionChangeRecord.STATUS_INVALID
        inst.save(update_fields=['status'])
    messages.success(request, '操作成功')


set_invalid.short_description = "设为无效"


class UserCommissionChangeRecordAdmin(OnlyViewAdmin):
    list_display = ['id', 'status', 'account', 'nickname', 'mobile', 'amount', 'show_type', 'source_type', 'create_at',
                    'desc']
    list_filter = ['source_type', 'show_type', 'status', 'create_at']
    search_fields = ['=order__order_no', '=account__user__mobile']
    readonly_fields = ['extra_info', 'order', 'card_order', 'theater_order']
    autocomplete_fields = ['account']
    list_per_page = 25
    actions = [export_usercommission, set_invalid]

    def nickname(self, obj):
        nickname = ''
        if obj.order:
            nickname = obj.order.user.last_name if obj.order.user else None
        elif obj.card_order:
            nickname = obj.card_order.card.user.last_name if obj.card_order.card.user else None
        elif obj.theater_order:
            nickname = obj.theater_order.user.last_name if obj.theater_order.user else None
        return nickname

    nickname.short_description = u'下单人昵称'

    def mobile(self, obj):
        mobile = ''
        if obj.order:
            mobile = obj.order.user.mobile if obj.order.user else None
        elif obj.card_order:
            mobile = obj.card_order.card.user.mobile if obj.card_order.card.user else None
        elif obj.theater_order:
            mobile = obj.theater_order.user.mobile if obj.theater_order.user else None
        return mobile

    mobile.short_description = u'下单人手机号'

    # def order_info(self, obj):
    #     if obj.order:
    #         return u'订单ID:{}, 下单人: {}, 订单号: {}'.format(obj.order.id, obj.order.user, obj.order.order_no)
    #     return ''
    #
    # order_info.short_description = u'订单信息'


class UserCommissionMonthRecordAdmin(OnlyViewAdmin):
    list_display = ['id', 'account', 'amount', 'year', 'month', 'show_type']
    list_filter = [YearFilter, MonthFilter, CardShowTypeFilter]
    search_fields = ['account__user__last_name', '=account__user__mobile']
    autocomplete_fields = ['account', 'show_type']


class UserAccountAdmin(ChangeAndViewAdmin):
    search_fields = ['=user__id', '=user__mobile']
    list_display = ['user', 'mobile', 'commission_balance', 'flag', 'level', 'parent', 'venue_display']
    list_filter = ['level', 'flag']
    exclude = ['version']
    readonly_fields = ['user']
    autocomplete_fields = ['level', 'venue']

    def parent(self, obj):
        return str(obj.user.parent) if obj.user.parent else None

    parent.short_description = u'上级'

    def mobile(self, obj):
        return obj.user.mobile

    mobile.short_description = u'手机'

    def venue_display(self, obj):
        return ', '.join([str(venue) for venue in obj.venue.all()])

    venue_display.short_description = u'场馆'

    def save_model(self, request, obj, form, change):
        if obj.level:
            account = UserAccount.objects.get(id=obj.id)
            if not account.level:
                from statistical.models import TotalStatistical
                TotalStatistical.add_agent_num()
        if not change:
            # same as super implement
            obj.save()
        else:
            if 'venue' in form.changed_data:
                form.changed_data.remove('venue')
            obj.save(update_fields=form.changed_data)


class UserAccountLevelAdmin(RemoveDeleteModelAdmin):
    list_display = ['name', 'grade', 'share_ratio', 'team_ratio', 'card_ratio']
    search_fields = ['name']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['grade', 'slug']
        return []


class ReceiptAccountAdmin(RemoveDeleteModelAdmin):
    pass


def audit_withdraw(modeladmin, request, queryset):
    queryset = queryset.filter(status=CommissionWithdraw.STAT_SUBMIT)
    try:
        for withdraw in queryset:
            withdraw.pay_type = CommissionWithdraw.PAY_TYPE_COMPANY
            withdraw.save(update_fields=['pay_type'])
            withdraw.approve()
    except WeChatPayException as e:
        messages.error(request, '{}'.format(e))


audit_withdraw.short_description = "支付此提现申请"


class PointWithdrawAdmin(RemoveDeleteModelAdmin):
    list_display = ['account', 'amount', 'status', 'create_at']
    list_filter = ['status']
    actions = [audit_withdraw]


def _write_row_by_xlwt(ws, cells, row_index):
    """
    :param ws:
    :param cells: cell values
    :param row_index: 1-relative row index
    :return:
    """
    for col, cell in enumerate(cells, 0):
        ws.write(row_index - 1, col, cell)


def export_withdraw_record(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')

    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('提现记录',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('提现记录')
    row_index = 1
    _write_row_by_xlwt(ws, [u'用户名', u'金额', u'状态', u'申请时间', u'交易单号'], row_index)
    row_index += 1
    for record in queryset:
        data = ['{}'.format(record.account), record.amount, record.get_status_display(),
                record.create_at.strftime('%Y%m%d%H%M%S'), record.trade_no]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


export_withdraw_record.short_description = '导出选中的提现记录'


def set_withdraw_paid(modeladmin, request, queryset):
    from statistical.models import TotalStatistical
    qs = queryset.filter(status=CommissionWithdraw.STAT_SUBMIT)
    withdraw_amount = 0
    for inst in qs:
        withdraw_amount += inst.amount + inst.fees
    TotalStatistical.change_award_stl(withdraw_amount=withdraw_amount)
    qs.update(status=CommissionWithdraw.STAT_APPROVED)
    messages.success(request, '操作成功')


set_withdraw_paid.short_description = '设置为已打款'


def check_origin(modeladmin, request, queryset):
    if queryset.count() > 1:
        messages.error(request, '每次只能选择一条查看')
    else:
        from django.http import HttpResponseRedirect
        from mall.mall_conf import admin_url_site_name
        return HttpResponseRedirect('/{}/shopping_points/usercommissionchangerecord/'.format(admin_url_site_name))


check_origin.short_description = '查看佣金来源'


class CommissionWithdrawAdmin(OnlyViewAdmin):
    search_fields = ['=account__user__mobile']
    list_display = ['account', 'amount', 'fees', 'status', 'create_at', 'trade_no']
    list_filter = ['status', 'create_at']
    actions = [set_withdraw_paid, export_withdraw_record]

    # def show_receipt_account(self, obj):
    #     return obj.account.withdraw_receipt_account()
    #
    # show_receipt_account.short_description = u'提现账户'

    # def check_origin(self, obj):
    #     from django.http import HttpResponseRedirect
    #     from mall.mall_conf import admin_url_site_name
    #     from django.utils.html import format_html
    #     return format_html("<a href='{url}'>查看佣金来源</a>",
    #                        url='/{}/shopping_points/usercommissionchangerecord/'.format(admin_url_site_name))
    #
    # check_origin.short_description = '操作'


admin.site.register(UserAccount, UserAccountAdmin)
admin.site.register(UserAccountLevel, UserAccountLevelAdmin)
admin.site.register(UserCommissionChangeRecord, UserCommissionChangeRecordAdmin)
admin.site.register(UserCommissionMonthRecord, UserCommissionMonthRecordAdmin)
admin.site.register(CommissionWithdraw, CommissionWithdrawAdmin)

technology_admin.register(UserAccount, UserAccountAdmin)
technology_admin.register(UserAccountLevel, UserAccountLevelAdmin)
technology_admin.register(UserCommissionChangeRecord, UserCommissionChangeRecordAdmin)
technology_admin.register(UserCommissionMonthRecord, UserCommissionMonthRecordAdmin)
technology_admin.register(CommissionWithdraw, CommissionWithdrawAdmin)
