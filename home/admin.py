from django.contrib import admin

from home.models import Home


@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        pass

    def has_delete_permission(self, request, obj=None):
        pass

    def has_change_permission(self, request, obj=None):
        pass
