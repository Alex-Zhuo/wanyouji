# coding=utf-8
from django.contrib import admin
from simpleui.admin import AjaxAdmin

from dj import technology_admin
from coupon.models import UserCouponRecord, Coupon, UserCouponImport, UserCouponCacheRecord, CouponBasic, \
    CouponActivity, CouponOrder, CouponOrderRefund, CouponReceipt
from dj_ext.permissions import RemoveDeleteModelAdmin, OnlyViewAdmin, AddAndViewAdmin, ChangeAndViewAdmin
from django.contrib import messages
from dj_ext import AdminException
from django.utils import timezone
from openpyxl import Workbook
from django.http import HttpResponse, JsonResponse
from caches import run_with_lock, get_redis_name
from django.utils.safestring import mark_safe


class CouponBasicAdmin(RemoveDeleteModelAdmin):
    def changelist_view(self, request, extra_context=None):
        obj = CouponBasic.get()
        if obj:
            return self.change_view(request, str(obj.id))
        return self.add_view(request, extra_context={'show_save_and_add_another': False})


def set_on(modeladmin, request, queryset):
    qs = queryset.filter(status=Coupon.STATUS_OFF)
    for obj in qs:
        obj.coupon_redis_stock()
    qs.update(status=Coupon.STATUS_ON)

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
        if not change:
            obj.save()
        else:
            if 'shows' in form.changed_data:
                form.changed_data.remove('shows')
            obj.save(update_fields=form.changed_data)
        if not change:
            Coupon.del_pop_up()


class UserCouponRecordAdmin(OnlyViewAdmin):
    list_display = ['no', 'user', 'coupon', 'status', 'expire_time', 'used_time', 'create_at', 'order']
    list_filter = ['status', 'expire_time', 'coupon']
    search_fields = ['=user__mobile']


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
    list_display = ['no', 'title', 'coupons_desc', 'status', 'create_at', 'update_at', 'url_link']
    autocomplete_fields = ['coupons']
    actions = [act_set_on, act_set_off, refresh_url_link]
    readonly_fields = ['no', 'url_link', 'update_at']

    def save_model(self, request, obj, form, change):
        obj.update_at = timezone.now()
        ret = super(CouponActivityAdmin, self).save_model(request, obj, form, change)
        if not obj.url_link:
            obj.get_url_link()
        return ret

    def coupons_desc(self, obj):
        data_list = list(obj.coupons.all().values_list('name', flat=True))
        if len(data_list) > 5:
            ret = ','.join(data_list[:5]) + '...'
        else:
            ret = ','.join(data_list[:5])
        return ret

    coupons_desc.short_description = '消费券'

    # def url_link_s(self, obj):
    #     return obj.url_link
    #
    # url_link_s.short_description = '领取链接'


def export_coupon_order(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}.xlsx"'.format(
        timezone.now().strftime('%Y%m%d%H%M'))
    wb = Workbook()
    ws = wb.active
    ws.append(['订单号', '用户', '手机号', '消费卷', '实付金额', '数量', '状态', '创建时间', '付款时间', '微信支付单号', '已退款金额', '退款时间'])
    for record in queryset:
        create_at = record.create_at.strftime('%Y-%m-%d %H:%M')
        pay_at = record.pay_at.strftime('%Y-%m-%d %H:%M') if record.pay_at else None
        refund_at = record.refund_at.strftime('%Y-%m-%d %H:%M') if record.refund_at else None
        data = [record.order_no, str(record.user), record.mobile, record.coupon_name, record.amount, record.multiply,
                record.get_status_display(), create_at, pay_at, record.transaction_id, record.refund_amount, refund_at]
        ws.append(data)
    wb.save(response)
    return response


export_coupon_order.short_description = '导出选中记录'


def coupon_set_paid(modeladmin, request, queryset):
    queryset = queryset.filter(status=CouponOrder.ST_DEFAULT)
    for order in queryset:
        order.set_paid()
    messages.success(request, '执行成功')


coupon_set_paid.short_description = u'后台付款'


class CouponOrderAdmin(AjaxAdmin, OnlyViewAdmin):
    list_display = ['order_no', 'user', 'mobile', 'coupon', 'amount', 'multiply', 'status', 'create_at', 'pay_at',
                    'transaction_id', 'op']
    search_fields = ['=transaction_id', '=mobile', '=order_no', 'coupon_name']
    list_filter = ['status', 'pay_at']
    readonly_fields = ['user', 'receipt', 'order_no', 'coupon']
    actions = ['coupon_refund', export_coupon_order, coupon_set_paid]

    def op(self, obj):
        html = ''
        if obj.status in CouponOrder.can_refund_status():
            html = '<button type="button" class="el-button el-button--success el-button--small item_coupon_refund" ' \
                   'style="margin-top:8px" alt={}>申请退款</button><br>'.format(obj.id)
        return mark_safe(html)

    op.short_description = '操作'

    def coupon_refund(self, request, queryset):
        qs = queryset.filter(status__in=CouponOrder.can_refund_status())
        if not qs:
            return JsonResponse(data={
                'status': 'error',
                'msg': '只有已付款可以退款！'
            })
        if qs.count() > 1:
            return JsonResponse(data={
                'status': 'error',
                'msg': '每次最多执行一条记录！'
            })
        coupon_order = queryset.first()
        key = get_redis_name('coupon_refund{}'.format(coupon_order.id))
        with run_with_lock(key, 3) as got:
            if not got:
                return JsonResponse(data={
                    'status': 'error',
                    'msg': '请勿点击多次！'
                })
        post = request.POST
        refund_reason = post.get('reason')
        refund_amount = coupon_order.amount - coupon_order.refund_amount
        if refund_amount <= 0:
            return JsonResponse(data={
                'status': 'error',
                'msg': '退款金额错误'
            })
        st, msg = coupon_order.do_refund(request.user, refund_reason)
        if not st:
            return JsonResponse(data={
                'status': 'error',
                'msg': msg
            })
        return JsonResponse(data={
            'status': 'success',
            'msg': '操作成功！'
        })

    coupon_refund.short_description = '申请退款'
    coupon_refund.type = 'success'
    coupon_refund.icon = 'el-icon-s-promotion'
    # 指定为弹出层，这个参数最关键
    coupon_refund.layer = {
        # 弹出层中的输入框配置
        # 这里指定对话框的标题
        'title': '消费券申请退款',
        # 提示信息
        'tips': '消费券退款后，实付金额将原路返回给用户，确认执行退款吗',
        # 确认按钮显示文本
        'confirm_button': '确认提交',
        # 取消按钮显示文本
        'cancel_button': '取消',
        # 弹出层对话框的宽度，默认50%
        'width': '50%',
        # 表单中 label的宽度，对应element-ui的 label-width，默认80px
        'labelWidth': "100px",
        'params': [
            {
                # 这里的type 对应el-input的原生input属性，默认为input
                'require': True,
                'type': 'input',
                # key 对应post参数中的key
                'key': 'reason',
                # 显示的文本
                'label': '退款原因',
                'width': '70%',
                # 表单中 label的宽度，对应element-ui的 label-width，默认80px
                'labelWidth': "120px",
            }
        ]
    }


def cancel_refund(modeladmin, request, queryset):
    inst = queryset.first()
    if inst.status == CouponOrderRefund.STATUS_DEFAULT:
        inst.set_cancel(request.user)
    messages.success(request, '执行成功')


cancel_refund.short_description = u'取消退款'


def confirm_refund(modeladmin, request, queryset):
    inst = queryset.filter(status__in=CouponOrderRefund.can_confirm_status()).first()
    if inst:
        from caches import run_with_lock
        key = get_redis_name('cprd_{}'.format(inst.id))
        with run_with_lock(key, 5) as got:
            if got:
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


confirm_refund.short_description = '确认退款'


class CouponOrderRefundAdmin(ChangeAndViewAdmin):
    list_display = ['order', 'out_refund_no', 'user', 'status', 'refund_amount', 'amount',
                    'refund_reason', 'error_msg', 'transaction_id', 'time_at', 'op']
    search_fields = ['=order_no', '=out_refund_no', '=transaction_id', '=user__mobile']
    list_filter = ['status', 'create_at']
    autocomplete_fields = ['user', 'order', 'op_user']
    actions = [confirm_refund, cancel_refund]
    readonly_fields = [f.name for f in CouponOrderRefund._meta.fields if
                       f.name not in ['refund_amount', 'refund_reason']]

    def time_at(self, obj):
        html = '<div style="width:300px"><p>创建时间：{}</p>'.format(
            obj.create_at.strftime('%Y-%m-%d %H:%M') if obj.create_at else '')
        html += '<p>确认时间：{}</p>'.format(obj.confirm_at.strftime('%Y-%m-%d %H:%M') if obj.confirm_at else '')
        html += '<p>完成时间：{}</p></div>'.format(obj.finish_at.strftime('%Y-%m-%d %H:%M') if obj.finish_at else '')
        return mark_safe(html)

    time_at.short_description = '时间'

    def op(self, obj):
        html = ''
        if obj.status in CouponOrderRefund.can_confirm_status():
            html = '<button type="button" class="el-button el-button--success el-button--small item_confirm_refund" ' \
                   'style="margin-top:8px" alt={}>确认退款</button><br>'.format(obj.id)
            html += '<button type="button" class="el-button el-button--warning el-button--small item_cancel_refund" ' \
                    'style="margin-top:8px" alt={}>取消退款</button><br>'.format(obj.id)
        return mark_safe(html)

    op.short_description = '操作'


class CouponReceiptAdmin(OnlyViewAdmin):
    list_display = ['payno', 'transaction_id', 'user', 'amount', 'status', 'pay_type', 'prepay_id']
    search_fields = ['payno', 'transaction_id']
    list_filter = ['status']
    readonly_fields = ['biz', 'user']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(CouponBasic, CouponBasicAdmin)
admin.site.register(Coupon, CouponAdmin)
admin.site.register(UserCouponRecord, UserCouponRecordAdmin)
admin.site.register(UserCouponImport, UserCouponImportAdmin)
admin.site.register(UserCouponCacheRecord, UserCouponCacheRecordAdmin)
admin.site.register(CouponActivity, CouponActivityAdmin)
admin.site.register(CouponOrder, CouponOrderAdmin)
admin.site.register(CouponOrderRefund, CouponOrderRefundAdmin)
admin.site.register(CouponReceipt, CouponReceiptAdmin)

technology_admin.register(CouponBasic, CouponBasicAdmin)
technology_admin.register(Coupon, CouponAdmin)
technology_admin.register(UserCouponRecord, UserCouponRecordAdmin)
technology_admin.register(UserCouponImport, UserCouponImportAdmin)
technology_admin.register(UserCouponCacheRecord, UserCouponCacheRecordAdmin)
technology_admin.register(CouponActivity, CouponActivityAdmin)
technology_admin.register(CouponOrder, CouponOrderAdmin)
technology_admin.register(CouponOrderRefund, CouponOrderRefundAdmin)
technology_admin.register(CouponReceipt, CouponReceiptAdmin)
