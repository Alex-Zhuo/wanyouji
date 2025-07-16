from django.contrib import admin

from dj import technology_admin
from dj_ext.middlewares import get_request
from django.utils.html import format_html

from dj_ext.permissions import RemoveDeleteModelAdmin, ChangeAndViewAdmin
from renovation.models import SubPages, Resource, ResourceImageItem, OpenScreenMedia, MediaType


# @admin.register(SubPages)
class SubPagesAdmin(admin.ModelAdmin):
    list_display = ['page_name', 'page_code', 'type', 'add_to_index', 'decorate_url', 'page_url']
    list_editable = ['add_to_index']

    def decorate_url(self, obj):
        request = get_request()
        url = request.build_absolute_uri(
            '/static/front/editor/index.html#/editor_mobile?page_name={}&page_code={}'.format(obj.page_name,
                                                                                              obj.page_code))
        return format_html(u'''<a onmouseover="this.style.color='orange'"
             onmouseout="this.style.color=''" href="{}" target="_blank">去装修</a>''', url)

    decorate_url.short_description = u'装修'

    def page_url(self, obj):
        request = get_request()
        return request.build_absolute_uri(
            '/static/front/store/?s=1#/activity?page_code={}'.format(obj.page_code))

    page_url.short_description = u'页面链接(用于装修)'


def set_on(modeladmin, request, queryset):
    for inst in queryset:
        inst.set_status(Resource.STATUS_ON)


set_on.short_description = u'上架'


def set_off(modeladmin, request, queryset):
    for inst in queryset:
        inst.set_status(Resource.STATUS_OFF)


set_off.short_description = u'下架'


class ResourceImageItemInlineAdmin(admin.TabularInline):
    model = ResourceImageItem
    extra = 0


class ResourceAdmin(ChangeAndViewAdmin):
    list_display = ['name', 'code', 'status']
    inlines = [ResourceImageItemInlineAdmin]
    actions = [set_on, set_off]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['code']
        return []


class MediaTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name']


class OpenScreenMediaAdmin(admin.ModelAdmin):
    list_display = ['id', 'media_type', 'image', 'video', 'seconds', 'is_use']
    list_filter = ['is_use']
    autocomplete_fields = ['media_type']


admin.site.register(MediaType, MediaTypeAdmin)
admin.site.register(OpenScreenMedia, OpenScreenMediaAdmin)
technology_admin.register(MediaType, MediaTypeAdmin)
technology_admin.register(OpenScreenMedia, OpenScreenMediaAdmin)
