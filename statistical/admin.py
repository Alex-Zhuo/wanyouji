from django.contrib import admin

from dj import technology_admin
from dj_ext.permissions import OnlyViewAdmin, OnlyReadTabularInline, CommonMultipleChoiceAdmin
from restframework_ext.filterbackends import YearFilter, MonthFilter, SessionFilter
from statistical.models import TotalStatistical, CityStatistical, DayStatistical, MonthSales, SessionAgentSum, \
    SessionSum, SessionAgentDaySum, SessionAgentRecord, SessionCpsDaySum, SessionCpsRecord
from django.http import HttpResponse
from django.utils import timezone
import xlwt
from dj_ext.exceptions import AdminException
import json


def _write_row_by_xlwt(ws, cells, row_index):
    """
    :param ws:
    :param cells: cell values
    :param row_index: 1-relative row index
    :return:
    """
    for col, cell in enumerate(cells, 0):
        ws.write(row_index - 1, col, cell)


class TotalStatisticalAdmin(OnlyViewAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = TotalStatistical.get_inst()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class CityStatisticalAdmin(OnlyViewAdmin):
    list_filter = ['city']
    list_display = ['city', 'order_num', 'total_amount']


class DayStatisticalAdmin(OnlyViewAdmin):
    list_filter = ['create_at']
    list_display = ['create_at', 'order_num', 'total_amount']


class MonthSalesAdmin(OnlyViewAdmin):
    list_filter = [YearFilter, MonthFilter]
    list_display = ['date', 'order_num', 'total_amount']

    def date(self, obj):
        return '{}-{}'.format(obj.year, obj.month)

    date.short_description = '日期'


class SessionAgentSumInline(OnlyReadTabularInline):
    model = SessionAgentSum
    extra = 0


def export_session_sum(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')

    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('场次销售统计',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('场次销售统计')
    row_index = 1
    _write_row_by_xlwt(ws, [u'演出项目', u'场次开演时间', u'代理', u'实付金额', u'佣金'], row_index)
    row_index += 1
    for dd in queryset:
        session = dd.session
        qs = SessionAgentSum.objects.filter(record_id=dd.id)
        for inst in qs:
            data = [str(session.show), session.start_at.strftime('%Y-%m-%d %H:%M'), str(inst.agent),
                    inst.amount, inst.c_amount]
            _write_row_by_xlwt(ws, data, row_index)
            row_index += 1
    wb.save(response)
    return response


export_session_sum.short_description = '导出选中记录'


class SessionSumAdmin(CommonMultipleChoiceAdmin, OnlyViewAdmin):
    list_display = ['session', 'total_amount', 'commission_amount']
    inlines = [SessionAgentSumInline]
    list_filter = [SessionFilter]
    actions = [export_session_sum]
    show_full_result_count = False
    readonly_fields = ['session']
    list_per_page = 20

    def total_amount(self, obj):
        return obj.session.actual_amount

    total_amount.short_description = '场次实付金额'

    def changelist_view(self, request, extra_context=None):
        res = super().changelist_view(request, extra_context=extra_context)
        if hasattr(res, 'context_data'):
            res.context_data['cl'].my_filter = json.dumps(dict(session__id=0))
        return res


def export_session_agent_day_sum(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')

    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('每日代理销售记录',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('每日代理销售记录')
    row_index = 1
    _write_row_by_xlwt(ws, [u'演出项目', u'场次开演时间', u'代理', '统计日期', '销售渠道', u'实付金额', u'佣金'], row_index)
    row_index += 1
    for inst in queryset:
        data = [str(inst.session.show), inst.session.start_at.strftime('%Y-%m-%d %H:%M'), str(inst.agent),
                inst.create_at.strftime('%Y-%m-%d'), inst.get_source_type_display(),
                inst.amount, inst.c_amount]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


export_session_agent_day_sum.short_description = '导出选中记录'


class SessionAgentDaySumAdmin(OnlyViewAdmin):
    list_display = ['session', 'agent', 'create_at', 'source_type', 'amount', 'c_amount']
    list_filter = [SessionFilter, 'source_type', 'create_at']
    search_fields = ['=agent__mobile', '=agent__first_name']
    actions = [export_session_agent_day_sum]
    readonly_fields = ['session', 'agent']
    show_full_result_count = False
    list_per_page = 20
    list_select_related = ['session', 'agent']


class SessionAgentRecordAdmin(OnlyViewAdmin):
    pass


def export_session_cps_day_sum(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.ms-excel')

    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('每日达人销售记录',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('每日达人销售记录')
    row_index = 1
    _write_row_by_xlwt(ws, [u'演出项目', u'场次开演时间', u'带货达人', '统计日期', '平台', '销售渠道', u'实付金额', u'佣金'], row_index)
    row_index += 1
    for inst in queryset:
        data = [str(inst.session.show), inst.session.start_at.strftime('%Y-%m-%d %H:%M'), inst.tiktok_nickname,
                inst.create_at.strftime('%Y-%m-%d'), inst.get_platform_display(), inst.get_source_type_display(),
                inst.amount, inst.c_amount]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


export_session_cps_day_sum.short_description = '导出选中记录'


class SessionCpsDaySumAdmin(OnlyViewAdmin):
    list_display = ['session', 'tiktok_nickname', 'tiktok_douyinid', 'create_at', 'source_type', 'platform', 'amount',
                    'c_amount']
    list_filter = [SessionFilter, 'platform', 'source_type', 'create_at']
    search_fields = ['=tiktok_douyinid', '=tiktok_nickname']
    actions = [export_session_cps_day_sum]
    readonly_fields = ['session']
    show_full_result_count = False
    list_per_page = 20
    list_select_related = ['session']


class SessionCpsRecordAdmin(OnlyViewAdmin):
    pass


admin.site.register(TotalStatistical, TotalStatisticalAdmin)
admin.site.register(CityStatistical, CityStatisticalAdmin)
admin.site.register(DayStatistical, DayStatisticalAdmin)
admin.site.register(MonthSales, MonthSalesAdmin)

technology_admin.register(TotalStatistical, TotalStatisticalAdmin)
technology_admin.register(CityStatistical, CityStatisticalAdmin)
technology_admin.register(DayStatistical, DayStatisticalAdmin)
technology_admin.register(MonthSales, MonthSalesAdmin)

admin.site.register(SessionSum, SessionSumAdmin)
admin.site.register(SessionAgentDaySum, SessionAgentDaySumAdmin)
admin.site.register(SessionAgentRecord, SessionAgentRecordAdmin)
admin.site.register(SessionCpsDaySum, SessionCpsDaySumAdmin)
admin.site.register(SessionCpsRecord, SessionCpsRecordAdmin)
technology_admin.register(SessionSum, SessionSumAdmin)
technology_admin.register(SessionAgentDaySum, SessionAgentDaySumAdmin)
technology_admin.register(SessionAgentRecord, SessionAgentRecordAdmin)
technology_admin.register(SessionCpsDaySum, SessionCpsDaySumAdmin)
technology_admin.register(SessionCpsRecord, SessionCpsRecordAdmin)
