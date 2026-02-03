from django.contrib import admin

# Register your models here.
from dj import technology_admin


from log.models import LogEntryMy


class LogEntryMyAdmin(admin.ModelAdmin):
    search_fields = ['object_id', 'object_repr', 'change_message']
    list_display = ['action_time', 'user', 'content_type', 'object_id', 'object_repr', 'show_action_flag',
                    'change_message_m']
    list_filter = ['content_type', 'action_time', 'action_flag']

    def get_actions(self, request):
        return []

    def change_message_m(self, obj):
        try:
            return eval(obj.change_message)
        except Exception as e:
            return obj.change_message

    change_message_m.short_description = '操作内容'

    def show_action_flag(self, obj):
        if obj.is_addition():
            return '新增'
        elif obj.is_change():
            return '修改'
        elif obj.is_deletion():
            return '删除'
        else:
            return '未知'

    show_action_flag.short_description = '操作'

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(LogEntryMy, LogEntryMyAdmin)
technology_admin.register(LogEntryMy, LogEntryMyAdmin)
