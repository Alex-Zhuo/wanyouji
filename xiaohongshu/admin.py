# coding=utf-8
from django.contrib import admin
from django.contrib import messages
from dj import technology_admin
from dj_ext.permissions import TechnologyModelAdmin, OnlyViewAdmin, RemoveDeleteModelAdmin
from dj_ext.exceptions import AdminException
from xiaohongshu.models import XiaoHongShuWxa, XhsUser, XhsShowThirdCategory, XhsOrder, XhsVoucherCodeRecord, XhsPoi
import logging

logger = logging.getLogger(__name__)


class XiaoHongShuWxaAdmin(TechnologyModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = XiaoHongShuWxa.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


def pull_poi(modeladmin, request, queryset):
    from caches import check_lock_time_out
    try:
        check_lock_time_out('pull_poi')
    except Exception as e:
        raise AdminException('请勿重复点击')
    XhsPoi.get_poi_list()
    messages.success(request, '刷新成功')


pull_poi.short_description = u'刷新Poi'


class XhsPoiAdmin(RemoveDeleteModelAdmin):
    list_display = ['name', 'poi_id', 'address']
    search_fields = ['name', 'poi_id']
    actions = [pull_poi]


class XhsUserAdmin(TechnologyModelAdmin):
    list_display = ['user', 'openid_xhs']
    exclude = ['session_key']
    search_fields = ['openid_xhs']


class XhsShowThirdCategoryAdmin(OnlyViewAdmin):
    list_display = ['name', 'category_id', 'second']
    search_fields = ['name']


def check_query_settle(modeladmin, request, queryset):
    for inst in queryset:
        try:
            inst.query_settle()
        except Exception as e:
            raise AdminException(e)
    messages.success(request, '执行成功')


check_query_settle.short_description = u'刷新结算状态'


class XhsOrderAdmin(OnlyViewAdmin):
    list_display = ['ticket_order', 'session', 'order_id']
    readonly_fields = ['ticket_order', 'session']

    def has_change_permission(self, request, obj=None):
        return False


class XhsVoucherCodeRecordAdmin(OnlyViewAdmin):
    list_display = ['ticket_order', 'voucher_code', 'xhs_check', 'msg']

    def has_change_permission(self, request, obj=None):
        return False


# admin.site.register(XiaoHongShuWxa, XiaoHongShuWxaAdmin)
# admin.site.register(XhsPoi, XhsPoiAdmin)
# admin.site.register(XhsUser, XhsUserAdmin)
# admin.site.register(XhsShowThirdCategory, XhsShowThirdCategoryAdmin)
# admin.site.register(XhsOrder, XhsOrderAdmin)
# admin.site.register(XhsVoucherCodeRecord, XhsVoucherCodeRecordAdmin)
#
# technology_admin.register(XiaoHongShuWxa, XiaoHongShuWxaAdmin)
# technology_admin.register(XhsPoi, XhsPoiAdmin)
# technology_admin.register(XhsUser, XhsUserAdmin)
# technology_admin.register(XhsShowThirdCategory, XhsShowThirdCategoryAdmin)
# technology_admin.register(XhsOrder, XhsOrderAdmin)
# technology_admin.register(XhsVoucherCodeRecord, XhsVoucherCodeRecordAdmin)
