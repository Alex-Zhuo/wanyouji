# coding=utf-8
from ai_agent.models import HistoryChat, DefaultQuestions
from django.contrib import admin
from dj import technology_admin
from dj_ext.permissions import OnlyViewAdmin, OnlyReadTabularInline
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


admin.site.register(DefaultQuestions, DefaultQuestionsAdmin)
admin.site.register(HistoryChat, HistoryChatAdmin)

technology_admin.register(DefaultQuestions, DefaultQuestionsAdmin)
technology_admin.register(HistoryChat, HistoryChatAdmin)
