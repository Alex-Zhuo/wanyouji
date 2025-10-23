# coding=utf-8
from django.contrib import admin
from dj import technology_admin
from coupon.models import UserCouponRecord, Coupon, UserCouponImport, UserCouponCacheRecord, CouponBasic, CouponActivity
from dj_ext.permissions import RemoveDeleteModelAdmin, OnlyViewAdmin, AddAndViewAdmin
from django.contrib import messages
from dj_ext import AdminException
from django.utils import timezone


class CouponBasicAdmin(RemoveDeleteModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = CouponBasic.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


def set_on(modeladmin, request, queryset):
    queryset.update(status=Coupon.STATUS_ON)
    messages.success(request, '执行成功')


set_on.short_description = '批量上架'


def set_off(modeladmin, request, queryset):
    queryset.update(status=Coupon.STATUS_OFF)
    messages.success(request, '执行成功')


set_off.short_description = '批量下架'


def clear_pop_up_cache(modeladmin, request, queryset):
    Coupon.del_pop_up()
    messages.success(request, '执行成功')


clear_pop_up_cache.short_description = '清除弹窗缓存'


class CouponAdmin(RemoveDeleteModelAdmin):
    list_display = ['no', 'name', 'amount', 'pay_amount', 'stock', 'discount', 'require_amount', 'require_num',
                    'expire_time', 'status',
                    'user_obtain_limit', 'create_at', 'update_at']
    list_filter = ['expire_time', 'limit_show_types_second', 'status']
    autocomplete_fields = ['shows', 'limit_show_types_second']
    readonly_fields = ['no']
    actions = [set_on, set_off, clear_pop_up_cache]
    search_fields = ['name', 'no']

    def save_model(self, request, obj, form, change):
        ret = super(CouponAdmin, self).save_model(request, obj, form, change)
        if not change:
            Coupon.del_pop_up()
        return ret


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


def act_set_on(modeladmin, request, queryset):
    queryset.update(status=CouponActivity.ST_ON, update_at=timezone.now())
    messages.success(request, '执行成功')


act_set_on.short_description = '批量上架'


def act_set_off(modeladmin, request, queryset):
    queryset.update(status=CouponActivity.ST_OFF, update_at=timezone.now())
    messages.success(request, '执行成功')


act_set_off.short_description = '批量下架'


def refresh_url_link(modeladmin, request, queryset):
    for obj in queryset:
        obj.get_url_link(True)
    messages.success(request, '执行成功')


refresh_url_link.short_description = '刷新领取链接'


class CouponActivityAdmin(admin.ModelAdmin):
    list_display = ['no', 'title', 'coupons_desc', 'status', 'create_at', 'update_at', 'url_link_s']
    autocomplete_fields = ['coupons']
    actions = [set_on, set_off, refresh_url_link]
    readonly_fields = ['no', 'url_link']

    def save_model(self, request, obj, form, change):
        obj.update_at = timezone.now()
        super(CouponActivityAdmin, self).save_model(request, obj, form, change)

    def coupons_desc(self, obj):
        data_list = list(obj.coupons.all().values_list('name', flat=True))
        if len(data_list) > 5:
            ret = ','.join(data_list[:5]) + '...'
        else:
            ret = ','.join(data_list[:5])
        return ret

    coupons_desc.short_description = '消费券'

    def url_link_s(self, obj):
        return None
        # return obj.get_url_link()

    url_link_s.short_description = '领取链接'


admin.site.register(CouponBasic, CouponBasicAdmin)
admin.site.register(Coupon, CouponAdmin)
admin.site.register(UserCouponRecord, UserCouponRecordAdmin)
admin.site.register(UserCouponImport, UserCouponImportAdmin)
admin.site.register(UserCouponCacheRecord, UserCouponCacheRecordAdmin)
admin.site.register(CouponActivity, CouponActivityAdmin)

technology_admin.register(CouponBasic, CouponBasicAdmin)
technology_admin.register(Coupon, CouponAdmin)
technology_admin.register(UserCouponRecord, UserCouponRecordAdmin)
technology_admin.register(UserCouponImport, UserCouponImportAdmin)
technology_admin.register(UserCouponCacheRecord, UserCouponCacheRecordAdmin)
technology_admin.register(CouponActivity, CouponActivityAdmin)
