# coding: utf-8
from __future__ import unicode_literals
from django.contrib import admin
from django.db.models import Q
from mall.models import User
from dj import technology_admin


class PermissionUtils(object):
    @classmethod
    def Q_change_perm(cls):
        return Q(codename__startswith='change')

    @classmethod
    def Q_exclude_delete_perm(cls):
        return ~Q(codename__startswith='delete')

    @classmethod
    def Q_exclude_add_perm(cls):
        return ~Q(codename__startswith='add')


class PermissionModelAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        qs = super(PermissionModelAdmin, self).get_queryset(request)
        if request.user.role == User.ROLE_STORE:
            if hasattr(qs.model, 'vendor'):
                return qs.filter(vendor__relate_user=request.user)
            elif hasattr(qs.model, 'account'):
                return qs.filter(account=request.user.account)
            else:
                return qs.filter(user=request.user)
        else:
            return qs

    def get_exclude(self, request, obj=None):
        """
        auto remove the operator field in change view, which will let the operator auto set but
        set by admin user in change_view form.
        :param request:
        :type request:
        :param obj:
        :type obj:
        :return:
        :rtype:
        """
        exclude = super(PermissionModelAdmin, self).get_exclude(request, obj)
        if request.user.role == User.ROLE_STORE:
            if hasattr(self.model, 'vendor'):
                exclude = list(set((exclude or []) + ['vendor']))
            return exclude
        return exclude

    def save_model(self, request, obj, form, change):
        if hasattr(request.user, 'vendor') and request.user.vendor is not None:
            obj.vendor = request.user.vendor
        super(PermissionModelAdmin, self).save_model(request, obj, form, change)


class SaveSignalAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if change:
            obj.save(update_fields=form.changed_data)
        return super(SaveSignalAdmin, self).save_model(request, obj, form, change)


class CommonMultipleChoiceAdmin(admin.ModelAdmin):

    def get_changelist(self, request, **kwargs):
        """
        Return the ChangeList class for use on the changelist page.
        """
        from dj_ext.AdminMixins import RewriteChangeList
        return RewriteChangeList


class RemoveDeleteModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        from caches import with_redis, save_model_key
        key = save_model_key.format(request.user.id)
        with with_redis() as redis:
            if redis.setnx(key, 1):
                redis.expire(key, 3)
            else:
                from dj_ext.exceptions import AdminException
                raise AdminException('请勿重复点击')
        return super(RemoveDeleteModelAdmin, self).save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return request.user and request.user.is_active and request.user.is_staff and (
                request.user.has_delete and request.user.is_superuser) or self.admin_site == technology_admin


class TechnologyModelAdmin(RemoveDeleteModelAdmin):
    def has_module_permission(self, request):
        # 控制总权限的
        return request.user and request.user.is_active and request.user.is_staff and self.admin_site == technology_admin


class ChangeAndViewAdmin(RemoveDeleteModelAdmin):
    def has_add_permission(self, request):
        return request.user and request.user.is_active and request.user.is_staff and self.admin_site == technology_admin


class OnlyViewAdmin(ChangeAndViewAdmin):
    def has_change_permission(self, request, obj=None):
        return request.user and request.user.is_active and request.user.is_staff and self.admin_site == technology_admin


class RemoveDeleteTabularInline(admin.TabularInline):
    def has_delete_permission(self, request, obj=None):
        return request.user and request.user.is_active and request.user.is_staff and (
                request.user.has_delete and request.user.is_superuser) or self.admin_site == technology_admin


class RemoveDeleteStackedInline(admin.StackedInline):
    def has_delete_permission(self, request, obj=None):
        return request.user and request.user.is_active and request.user.is_staff and (
                request.user.has_delete and request.user.is_superuser) or self.admin_site == technology_admin


class OnlyReadTabularInline(RemoveDeleteTabularInline):
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj):
        return False


class OnlyReadStackedInline(RemoveDeleteStackedInline):
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj):
        return False
