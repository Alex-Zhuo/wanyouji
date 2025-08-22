# coding=utf-8
from django.contrib import admin
from dj import technology_admin
from coupon.models import UserCouponRecord, Coupon
from dj_ext.permissions import RemoveDeleteModelAdmin, OnlyViewAdmin
from django.contrib import messages


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


class UserCouponRecordAdmin(OnlyViewAdmin):
    list_display = ['no', 'user', 'coupon', 'status', 'expire_time', 'used_time', 'create_at', 'order']
    list_filter = ['status', 'expire_time']


admin.site.register(Coupon, CouponAdmin)
admin.site.register(UserCouponRecord, UserCouponRecordAdmin)

technology_admin.register(Coupon, CouponAdmin)
technology_admin.register(UserCouponRecord, UserCouponRecordAdmin)
