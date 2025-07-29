# coding=utf-8
from ai_agent.models import HistoryChatDetail, HistoryChat, DefaultQuestions
from django.contrib import admin
from dj import technology_admin
from dj_ext.permissions import OnlyViewAdmin, OnlyReadTabularInline


class DefaultQuestionsAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_use', 'display_order', 'create_at']
    list_editable = ['display_order']
    list_filter = ['is_use']


class HistoryChatDetailInline(OnlyReadTabularInline):
    model = HistoryChatDetail
    extra = 0


class HistoryChatAdmin(OnlyViewAdmin):
    list_display = ['user', 'update_at']
    inlines = [HistoryChatDetailInline]

admin.site.register(DefaultQuestions, DefaultQuestionsAdmin)
admin.site.register(HistoryChat, HistoryChatAdmin)

technology_admin.register(DefaultQuestions, DefaultQuestionsAdmin)
technology_admin.register(HistoryChat, HistoryChatAdmin)