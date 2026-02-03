# coding=utf-8
from django.contrib import admin
from django.contrib import messages
from dj import technology_admin
from dj_ext.permissions import RemoveDeleteModelAdmin, TechnologyModelAdmin, OnlyReadTabularInline, OnlyViewAdmin
from kuaishou_wxa.models import KShouWxa, KsStore, KsPoi, KsPoiService, KsShowThirdCategory, KsShowTopCategory, \
    KsShowSecondaryCategory, KShouPlatform, KsPoiQualityLabels, KsOrderReportRecord, KsOrderSettleRecord, KsUser
from dj_ext.exceptions import AdminException
import logging
from django.db.models import F

logger = logging.getLogger(__name__)


class KShouWxaAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = KShouWxa.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class KShouPlatformAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = KShouPlatform.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class KsUserAdmin(TechnologyModelAdmin):
    list_display = ['user', 'openid_ks']
    exclude = ['session_key']
    search_fields = ['openid_ks']
    readonly_fields = ['user']

class KsPoiInline(admin.TabularInline):
    model = KsPoi
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['is_merge', 'new_poi_id']
        return self.readonly_fields


def pull_poi(modeladmin, request, queryset):
    if queryset.count() > 10:
        raise AdminException('每次最多拉取10个店铺')
    for inst in queryset:
        inst.get_poi_list()
    messages.success(request, '执行成功')


pull_poi.short_description = u'拉取店铺poi'


class KsStoreAdmin(RemoveDeleteModelAdmin):
    list_display = ['name', 'city']
    search_fields = ['name']
    inlines = [KsPoiInline]
    actions = [pull_poi]
    autocomplete_fields = ['city']

    def save_model(self, request, obj, form, change):
        if not obj.wxa:
            obj.wxa = KShouWxa.get()
        super(KsStoreAdmin, self).save_model(request, obj, form, change)


class KsPoiQualityLabelsAdmin(OnlyViewAdmin):
    list_filter = ['title']
    search_fields = ['title']


def check_poi_status(modeladmin, request, queryset):
    qs = queryset.filter(poi_id__isnull=False)
    if qs.count() > 20:
        raise AdminException('一次查询不可超过20个')
    poi_ids = list(qs.values_list('poi_id', flat=True))
    try:
        KsPoiService.change_status(poi_ids)
    except Exception as e:
        raise AdminException(e)
    messages.success(request, '执行成功')


check_poi_status.short_description = u'刷新审核状态'


def push_approve(modeladmin, request, queryset):
    for inst in queryset:
        is_update = False if inst.status == KsPoiService.ST_DEFAULT else True
        try:
            inst.poi_mount(is_update=is_update)
        except Exception as e:
            raise AdminException(e)
    messages.success(request, '执行成功')


push_approve.short_description = u'推送审核'


class KsPoiServiceAdmin(RemoveDeleteModelAdmin):
    list_display = ['kspoi', 'status', 'create_at']
    search_fields = ['=poi_id']
    list_filter = ['status']
    actions = [push_approve, check_poi_status]
    autocomplete_fields = ['quality_labels']

    def get_exclude(self, request, obj=None):
        if not obj:
            return ['status', 'reject_reason']
        return []

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['status', 'reject_reason']
        return []

    def save_model(self, request, obj, form, change):
        if not obj.poi_id:
            obj.wxa = KShouWxa.get()
            obj.poi_id = obj.kspoi.poi_id
        ret = super(KsPoiServiceAdmin, self).save_model(request, obj, form, change)
        return ret

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        # 过滤外键的选择。
        if add and context['adminform'].form.fields.get('kspoi'):
            context['adminform'].form.fields['kspoi'].queryset = KsPoi.objects.filter(is_merge=False)
        return super(KsPoiServiceAdmin, self).render_change_form(request, context, add, change, form_url, obj)


class KsShowTopCategoryAdmin(OnlyViewAdmin):
    list_display = ['name', 'category_id']
    search_fields = ['name']


class KsShowSecondaryCategoryAdmin(OnlyViewAdmin):
    list_display = ['name', 'category_id', 'superior']
    search_fields = ['name']


class KsShowThirdCategoryAdmin(OnlyViewAdmin):
    list_display = ['name', 'category_id', 'enable', 'second']
    search_fields = ['name']


def check_query_settle(modeladmin, request, queryset):
    for inst in queryset:
        try:
            inst.query_settle()
        except Exception as e:
            raise AdminException(e)
    messages.success(request, '执行成功')


check_query_settle.short_description = u'刷新结算状态'


class KsOrderSettleRecordAdmin(OnlyViewAdmin):
    list_display = ['order', 'out_settle_no', 'reason', 'settle_amount', 'amount', 'settle_status', 'settle_no',
                    'error_msg', 'create_at']
    search_fields = ['=order_no', '=out_settle_no']
    list_filter = ['settle_status', 'create_at']
    actions = [check_query_settle]


def order_report(modeladmin, request, queryset):
    for inst in queryset.exclude(status=F('push_status')):
        st, msg = inst.order_report()
        if not st:
            raise AdminException(msg)
    messages.success(request, '执行成功')


order_report.short_description = u'同步核销状态'


class KsOrderReportRecordAdmin(OnlyViewAdmin):
    list_display = ['order', 'status', 'push_status', 'ks_settle', 'update_at']
    list_filter = ['push_status', 'ks_settle']
    search_fields = ['=order_no']
    actions = [order_report]
    autocomplete_fields = ['order']

#
# admin.site.register(KShouWxa, KShouWxaAdmin)
# admin.site.register(KsStore, KsStoreAdmin)
# admin.site.register(KsUser, KsUserAdmin)
# admin.site.register(KsPoiQualityLabels, KsPoiQualityLabelsAdmin)
# admin.site.register(KsPoiService, KsPoiServiceAdmin)
# admin.site.register(KsShowTopCategory, KsShowTopCategoryAdmin)
# admin.site.register(KsShowSecondaryCategory, KsShowSecondaryCategoryAdmin)
# admin.site.register(KsShowThirdCategory, KsShowThirdCategoryAdmin)
# admin.site.register(KShouPlatform, KShouPlatformAdmin)
# admin.site.register(KsOrderReportRecord, KsOrderReportRecordAdmin)
# admin.site.register(KsOrderSettleRecord, KsOrderSettleRecordAdmin)
#
# technology_admin.register(KShouWxa, KShouWxaAdmin)
# technology_admin.register(KsStore, KsStoreAdmin)
# technology_admin.register(KsUser, KsUserAdmin)
# technology_admin.register(KsPoiQualityLabels, KsPoiQualityLabelsAdmin)
# technology_admin.register(KsPoiService, KsPoiServiceAdmin)
# technology_admin.register(KsShowTopCategory, KsShowTopCategoryAdmin)
# technology_admin.register(KsShowSecondaryCategory, KsShowSecondaryCategoryAdmin)
# technology_admin.register(KsShowThirdCategory, KsShowThirdCategoryAdmin)
# technology_admin.register(KShouPlatform, KShouPlatformAdmin)
# technology_admin.register(KsOrderReportRecord, KsOrderReportRecordAdmin)
# technology_admin.register(KsOrderSettleRecord, KsOrderSettleRecordAdmin)
