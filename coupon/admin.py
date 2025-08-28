# coding=utf-8
from django.contrib import admin
from dj import technology_admin
from coupon.models import UserCouponRecord, Coupon, UserCouponImport, UserCouponCacheRecord
from dj_ext.permissions import RemoveDeleteModelAdmin, OnlyViewAdmin, AddAndViewAdmin
from django.contrib import messages
from dj_ext import AdminException


def set_on(modeladmin, request, queryset):
    queryset.update(status=Coupon.STATUS_ON)
    messages.success(request, '执行成功')


set_on.short_description = '批量上架'


def set_off(modeladmin, request, queryset):
    queryset.update(status=Coupon.STATUS_OFF)
    messages.success(request, '执行成功')


set_off.short_description = '批量下架'


class CouponAdmin(RemoveDeleteModelAdmin):
    list_display = ['no', 'name', 'amount', 'expire_time', 'status', 'user_obtain_limit', 'require_amount',
                    'create_at', 'update_at']
    list_filter = ['expire_time', 'limit_show_types_second', 'status']
    autocomplete_fields = ['shows', 'limit_show_types_second']
    readonly_fields = ['no']
    actions = [set_on, set_off]
    search_fields = ['name', 'no']


class UserCouponRecordAdmin(OnlyViewAdmin):
    list_display = ['no', 'user', 'coupon', 'status', 'expire_time', 'used_time', 'create_at', 'order']
    list_filter = ['status', 'expire_time']


def do_performance_import(modeladmin, request, queryset):
    qs = queryset.filter(status=UserCouponImport.ST_NEED)
    if not qs:
        raise AdminException('未执行的记录才能执行')
    for inst in qs:
        from coupon.q_tasks import coupon_import_task
        coupon_import_task(pk=inst.id)
    messages.success(request, '操作成功,正在执行')


do_performance_import.short_description = '执行导入'


class UserCouponImportAdmin(AddAndViewAdmin):
    list_display = [f.name for f in UserCouponImport._meta.fields]
    actions = [do_performance_import]
    readonly_fields = [f.name for f in UserCouponImport._meta.fields if f.name not in ['file', 'remark', 'status']]

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        super().save_model(request, obj, form, change)


class UserCouponCacheRecordAdmin(admin.ModelAdmin):
    list_display = [f.name for f in UserCouponCacheRecord._meta.fields]
    autocomplete_fields = ['coupon']
    search_fields = ['=mobile']
    list_filter = ['coupon']
    readonly_fields = ['record']


admin.site.register(Coupon, CouponAdmin)
admin.site.register(UserCouponRecord, UserCouponRecordAdmin)
admin.site.register(UserCouponImport, UserCouponImportAdmin)
admin.site.register(UserCouponCacheRecord, UserCouponCacheRecordAdmin)

technology_admin.register(Coupon, CouponAdmin)
technology_admin.register(UserCouponRecord, UserCouponRecordAdmin)
technology_admin.register(UserCouponImport, UserCouponImportAdmin)
technology_admin.register(UserCouponCacheRecord, UserCouponCacheRecordAdmin)
