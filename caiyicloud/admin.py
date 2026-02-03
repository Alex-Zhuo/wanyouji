# coding=utf-8
from django.contrib import admin
from django.contrib import messages

from caiyicloud.models import CaiYiCloudApp, CyCategory, CyVenue, CyShowEvent, CyDeliveryMethods, CyCheckInMethods, \
    CyIdTypes, CySession, CyTicketType, CyFirstCategory, CyOrder, CyTicketCode, CyOrderRefund, CyEventLog, CySessionLog, \
    PromoteRule, PromoteProduct, PromoteActivity
from dj import technology_admin
from dj_ext.permissions import TechnologyModelAdmin, OnlyViewAdmin, RemoveDeleteModelAdmin, OnlyReadTabularInline
from dj_ext.exceptions import AdminException
import logging

logger = logging.getLogger(__name__)


class AllOnlyViewAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CaiYiCloudAppAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = CaiYiCloudApp.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


class CyFirstCategoryAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyCategoryAdmin(AllOnlyViewAdmin):
    list_display = ['first_cate', 'code', 'name']
    list_filter = ['first_cate']


class CyVenueAdmin(AllOnlyViewAdmin):
    list_display = ['cy_no', 'venue', 'province_name', 'city_name']


def refresh_event(modeladmin, request, queryset):
    event_ids = list(queryset.values_list('event_id', flat=True))
    CyShowEvent.sync_create_event(event_ids, '后台节目刷新')
    messages.success(request, '执行成功,刷新中')


refresh_event.short_description = '刷新节目所有场次'


def pull_all_event(modeladmin, request, queryset):
    CyShowEvent.pull_all_event('后台执行全部拉取')
    messages.success(request, '执行成功,刷新中')


pull_all_event.short_description = '拉取所有项目'


def pull_new_event(modeladmin, request, queryset):
    CyShowEvent.pull_new_event('后台执行拉新拉取')
    messages.success(request, '执行成功,刷新中')


pull_new_event.short_description = '拉取新项目'


class CyShowEventAdmin(AllOnlyViewAdmin):
    list_display = ['event_id', 'show', 'category', 'show_type', 'seat_type', 'ticket_mode', 'state',
                    'expire_order_minute', 'updated_at', 'error_msg']
    list_filter = ['state', 'show_type', 'updated_at']
    actions = [refresh_event, pull_new_event, pull_all_event]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(is_delete=False)
        return qs


class CyIdTypesAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyCheckInMethodsAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyDeliveryMethodsAdmin(AllOnlyViewAdmin):
    list_display = ['code', 'name']


class CyTicketTypeInline(OnlyReadTabularInline):
    model = CyTicketType
    extra = 0
    exclude = ['ticket_pack_list']
    readonly_fields = ['ticket_pack_desc']

    def ticket_pack_desc(self, obj):
        ticket_pack_list = obj.ticket_pack_list.all()
        ret = ''
        if ticket_pack_list:
            for pack in ticket_pack_list:
                ct = CyTicketType.objects.filter(cy_no=pack.ticket_type_id).first()
                ret += f'({pack.ticket_type_id}){ct.name}-价格:{pack.price}-数量:{pack.qty},'
        return ret

    ticket_pack_desc.short_description = u'套票'


def refresh_session(modeladmin, request, queryset):
    if queryset.count() > 1:
        raise AdminException('每次最多刷新一场')
    inst = queryset.first()
    try:
        inst.refresh_session('后台场次刷新')
    except Exception as e:
        raise AdminException(e)
    messages.success(request, '执行成功')


refresh_session.short_description = '刷新场次'


class CySessionAdmin(AllOnlyViewAdmin):
    list_display = ['cy_no', 'event', 'c_session', 'start_time', 'end_time', 'sale_time', 'state',
                    'session_type', 'require_id_on_ticket', 'limit_on_session', 'limit_on_event', 'updated_at']
    list_filter = ['start_time', 'state', 'updated_at']
    inlines = [CyTicketTypeInline]
    actions = [refresh_session]


class PromoteRuleInline(OnlyReadTabularInline):
    model = PromoteRule
    extra = 0
    list_display = ['num', 'amount', 'discount_value']


class PromoteProductInline(OnlyReadTabularInline):
    model = PromoteProduct
    extra = 0
    list_display = ['event', 'session', 'ticket_type', 'must_session', 'scope_type']


def refresh_pro_act(modeladmin, request, queryset):
    if queryset.count() > 10:
        raise AdminException('每次最多刷新10条记录')
    for inst in queryset:
        try:
            inst.refresh_pro_activity()
        except Exception as e:
            raise AdminException(e)
    messages.success(request, '执行成功')


refresh_pro_act.short_description = '刷新营销活动'


def pull_new_pro_act(modeladmin, request, queryset):
    try:
        PromoteActivity.init_activity(True)
    except Exception as e:
        raise AdminException(e)
    messages.success(request, '执行成功')


pull_new_pro_act.short_description = '拉取新营销活动'


def promote_set_on(modeladmin, request, queryset):
    queryset.update(enabled=1)
    messages.success(request, '执行成功')


promote_set_on.short_description = '批量启用'


def promote_set_off(modeladmin, request, queryset):
    queryset.update(enabled=0)
    messages.success(request, '执行成功')


promote_set_off.short_description = '批量关闭'


class PromoteActivityAdmin(AllOnlyViewAdmin):
    list_display = ['act_id', 'name', 'category', 'type', 'enabled', 'start_time', 'end_time', 'display_name',
                    'description']
    inlines = [PromoteRuleInline, PromoteProductInline]
    actions = [refresh_pro_act, pull_new_pro_act, promote_set_on, promote_set_off]


class CyTicketCodeInline(OnlyReadTabularInline):
    model = CyTicketCode
    extra = 0


class CyOrderAdmin(AllOnlyViewAdmin):
    list_display = ['cy_order_no', 'ticket_order', 'cy_session', 'order_state', 'buyer_cellphone',
                    'auto_cancel_order_time', 'exchange_code',
                    'exchange_qr_code', 'code_type', 'delivery_method', 'created_at', 'updated_at']
    inlines = [CyTicketCodeInline]
    search_fields = ['cy_order_no']
    list_filter = ['order_state']


class CyOrderRefundAdmin(AllOnlyViewAdmin):
    list_display = ['apply_id', 'refund', 'cy_order', 'status', 'error_msg']


class CyEventLogAdmin(AllOnlyViewAdmin):
    list_display = ['event', 'title', 'create_at']


class CySessionLogAdmin(AllOnlyViewAdmin):
    list_display = ['session', 'title', 'create_at']


admin.site.register(CaiYiCloudApp, CaiYiCloudAppAdmin)
admin.site.register(CyFirstCategory, CyFirstCategoryAdmin)
admin.site.register(CyCategory, CyCategoryAdmin)
admin.site.register(CyVenue, CyVenueAdmin)
admin.site.register(CyShowEvent, CyShowEventAdmin)
admin.site.register(CyIdTypes, CyIdTypesAdmin)
admin.site.register(CyCheckInMethods, CyCheckInMethodsAdmin)
admin.site.register(CyDeliveryMethods, CyDeliveryMethodsAdmin)
admin.site.register(CySession, CySessionAdmin)
admin.site.register(PromoteActivity, PromoteActivityAdmin)
admin.site.register(CyOrder, CyOrderAdmin)
admin.site.register(CyOrderRefund, CyOrderRefundAdmin)
admin.site.register(CyEventLog, CyEventLogAdmin)
admin.site.register(CySessionLog, CySessionLogAdmin)

technology_admin.register(CaiYiCloudApp, CaiYiCloudAppAdmin)
technology_admin.register(CyFirstCategory, CyFirstCategoryAdmin)
technology_admin.register(CyCategory, CyCategoryAdmin)
technology_admin.register(CyVenue, CyVenueAdmin)
technology_admin.register(CyShowEvent, CyShowEventAdmin)
technology_admin.register(CyIdTypes, CyIdTypesAdmin)
technology_admin.register(CyCheckInMethods, CyCheckInMethodsAdmin)
technology_admin.register(CyDeliveryMethods, CyDeliveryMethodsAdmin)
technology_admin.register(CySession, CySessionAdmin)
technology_admin.register(PromoteActivity, PromoteActivityAdmin)
technology_admin.register(CyOrder, CyOrderAdmin)
technology_admin.register(CyOrderRefund, CyOrderRefundAdmin)
technology_admin.register(CyEventLog, CyEventLogAdmin)
technology_admin.register(CySessionLog, CySessionLogAdmin)
