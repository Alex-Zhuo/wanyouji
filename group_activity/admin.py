from django.contrib import admin

from dj import technology_admin
from dj_ext.permissions import ChangeAndViewAdmin
from .models import ActivityCategory, GroupActivity, ActivityImage, ActivityParticipant, GroupParticipantRefund
from django.utils.safestring import mark_safe
from dj_ext import AdminException
from django.contrib import messages


class ActivityImageInline(admin.TabularInline):
    model = ActivityImage
    extra = 1
    fields = ('image', 'is_primary', 'order')


class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_active',)
    search_fields = ('name',)


class GroupActivityAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'creator', 'category', 'status', 'current_members', 'required_members', 'registration_deadline')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'description', 'address')
    inlines = [ActivityImageInline]
    readonly_fields = ['no']
    fieldsets = (
        ('基本信息', {
            'fields': ('creator', 'title', 'description', 'category')
        }),
        ('活动详情', {
            'fields': ('required_members', 'contact_phone', 'address', 'latitude', 'longitude')
        }),
        ('时间设置', {
            'fields': ('registration_deadline',)
        }),
        ('状态', {
            'fields': ('status',)
        }),
    )


class ActivityParticipantAdmin(admin.ModelAdmin):
    list_display = ('activity', 'user', 'payment_status', 'payment_amount', 'joined_at')
    list_filter = ('payment_status', 'joined_at')
    search_fields = ('activity__title', 'user__username')


def set_confirm(modeladmin, request, queryset):
    inst = queryset.filter(status=GroupParticipantRefund.STATUS_DEFAULT).first()
    if inst:
        from caches import run_with_lock, ticket_order_refund_key
        with run_with_lock(ticket_order_refund_key, 5) as acquired:
            if acquired:
                try:
                    st, msg = inst.set_confirm(request.user)
                    if not st:
                        raise AdminException(msg)
                    messages.success(request, '执行成功')
                except Exception as e:
                    raise AdminException(str(e))
            else:
                messages.error(request, '请勿操作太快')
    else:
        messages.error(request, '待退款状态才可执行')


set_confirm.short_description = u'确认退款'


def set_cancel(modeladmin, request, queryset):
    inst = queryset.first()
    if inst.status in [GroupParticipantRefund.STATUS_DEFAULT, GroupParticipantRefund.STATUS_PAY_FAILED]:
        inst.set_cancel(request.user)
    messages.success(request, '执行成功')


set_cancel.short_description = u'取消退款'


class GroupParticipantRefundAdmin(ChangeAndViewAdmin):
    list_display = ['id', 'order', 'out_refund_no', 'user', 'status', 'refund_amount', 'amount',
                    'refund_reason', 'error_msg', 'transaction_id', 'time_at', 'op']
    search_fields = ['=order_no', '=out_refund_no', '=transaction_id']
    list_filter = ['status', 'create_at']
    autocomplete_fields = ['user', 'order', 'op_user']
    # actions = [set_confirm, set_cancel]
    readonly_fields = [f.name for f in GroupParticipantRefund._meta.fields if
                       f.name not in ['refund_amount', 'return_reason']]

    def time_at(self, obj):
        html = '<div style="width:300px"><p>创建时间：{}</p>'.format(
            obj.create_at.strftime('%Y-%m-%d %H:%M') if obj.create_at else '')
        html += '<p>确认时间：{}</p>'.format(obj.confirm_at.strftime('%Y-%m-%d %H:%M') if obj.confirm_at else '')
        html += '<p>完成时间：{}</p></div>'.format(obj.finish_at.strftime('%Y-%m-%d %H:%M') if obj.finish_at else '')
        return mark_safe(html)

    time_at.short_description = '时间'

    def op(self, obj):
        html = ''
        if obj.status == GroupParticipantRefund.STATUS_DEFAULT:
            html = '<button type="button" class="el-button el-button--success el-button--small item_set_confirm" ' \
                   'style="margin-top:8px" alt={}>确认退款</button><br>'.format(obj.id)
        if obj.status in [GroupParticipantRefund.STATUS_DEFAULT, GroupParticipantRefund.STATUS_PAY_FAILED]:
            html += '<button type="button" class="el-button el-button--warning el-button--small item_set_cancel" ' \
                    'style="margin-top:8px" alt={}>取消退款</button><br>'.format(obj.id)
        return mark_safe(html)

    op.short_description = '操作'


admin.site.register(ActivityCategory, ActivityCategoryAdmin)
admin.site.register(GroupActivity, GroupActivityAdmin)
admin.site.register(ActivityParticipant, ActivityParticipantAdmin)
admin.site.register(GroupParticipantRefund, GroupParticipantRefundAdmin)

technology_admin.register(ActivityCategory, ActivityCategoryAdmin)
technology_admin.register(GroupActivity, GroupActivityAdmin)
technology_admin.register(ActivityParticipant, ActivityParticipantAdmin)
technology_admin.register(GroupParticipantRefund, GroupParticipantRefundAdmin)
