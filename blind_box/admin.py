# coding=utf-8
from django.contrib import admin

from blind_box.models import Prize
from dj import technology_admin
from dj_ext.permissions import RemoveDeleteModelAdmin
from django.contrib import messages


def set_on(modeladmin, request, queryset):
    qs = queryset.filter(tatus=Prize.STATUS_OFF)
    qs.update(status=Prize.STATUS_ON)
    for obj in qs:
        obj.prize_redis_stock()
    messages.success(request, '执行成功')


set_on.short_description = '批量上架'


def set_off(modeladmin, request, queryset):
    qs = queryset.filter(tatus=Prize.STATUS_ON)
    qs.update(status=Prize.STATUS_OFF)
    for obj in qs:
        obj.prize_del_redis_stock()
    messages.success(request, '执行成功')


set_off.short_description = '批量下架'


class PrizeAdmin(RemoveDeleteModelAdmin):
    list_display = ['no', 'title', 'status', 'source_type', 'rare_type', 'amount', 'stock', 'weight', 'desc',
                    'create_at']
    list_filter = ['status', 'source_type', 'rare_type']
    search_fields = ['no']
    actions = [set_on, set_off]


admin.site.register(Prize, PrizeAdmin)

technology_admin.register(Prize, PrizeAdmin)
