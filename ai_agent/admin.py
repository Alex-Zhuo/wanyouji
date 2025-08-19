# coding=utf-8
from ai_agent.models import HistoryChat, DefaultQuestions, MoodImage, ImageResource, ImageResourceItem
from django.contrib import admin
from dj import technology_admin
from dj_ext.permissions import OnlyViewAdmin, OnlyReadTabularInline, ChangeAndViewAdmin
import json
from django.utils.safestring import mark_safe
from datetime import datetime


class DefaultQuestionsAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_use', 'display_order', 'create_at']
    list_editable = ['display_order']
    list_filter = ['is_use']


class HistoryChatAdmin(OnlyViewAdmin):
    list_display = ['user', 'create_at']
    # readonly_fields = ['chat']
    # exclude = ['content']
    #
    # def chat(self, obj):
    #     content = None
    #     if obj.content:
    #         html = '<div style="width:900px">'
    #         content_list = json.loads(obj.content)
    #         for cn in content_list:
    #             timestamp = int(int(cn['timestamp']) / 1000)
    #             date_at = datetime.fromtimestamp(timestamp)
    #             html += '<p>时间：{}</p>'.format(date_at)
    #             html += '<p>问题：{}</p>'.format(cn['question'])
    #             html += '<p>回答：{}</p>'.format(cn['answer'])
    #             html += '<p></p>'
    #         html += ' </div>'
    #         content = mark_safe(html)
    #     return content
    #
    # chat.short_description = '对话记录'


class MoodImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'image', 'code']


def set_on(modeladmin, request, queryset):
    for inst in queryset:
        inst.set_status(ImageResource.STATUS_ON)


set_on.short_description = u'上架'


def set_off(modeladmin, request, queryset):
    for inst in queryset:
        inst.set_status(ImageResource.STATUS_OFF)


set_off.short_description = u'下架'


class ImageResourceItemInlineAdmin(admin.TabularInline):
    model = ImageResourceItem
    extra = 0


class ImageResourceAdmin(ChangeAndViewAdmin):
    list_display = ['name', 'code', 'status']
    inlines = [ImageResourceItemInlineAdmin]
    actions = [set_on, set_off]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['code']
        return []


admin.site.register(DefaultQuestions, DefaultQuestionsAdmin)
admin.site.register(HistoryChat, HistoryChatAdmin)
admin.site.register(MoodImage, MoodImageAdmin)
admin.site.register(ImageResource, ImageResourceAdmin)

technology_admin.register(DefaultQuestions, DefaultQuestionsAdmin)
technology_admin.register(HistoryChat, HistoryChatAdmin)
technology_admin.register(MoodImage, MoodImageAdmin)
technology_admin.register(ImageResource, ImageResourceAdmin)
