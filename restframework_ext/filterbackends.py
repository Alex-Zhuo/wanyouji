# coding: utf-8
from django.contrib.admin import SimpleListFilter
from rest_framework.filters import BaseFilterBackend
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta


def filter_queryset_mixin(request, queryset, owner_field_names):
    model = queryset.model
    owner_field_name = None
    for ofn in owner_field_names:
        if hasattr(model, ofn):
            owner_field_name = ofn
            break
    if not owner_field_name:
        raise ValueError(u'找不到owner属性, %s' % owner_field_names)
    # assert isinstance(getattr(model, 'user', None) or getattr(model, 'owner', None).field, settings.AUTH_USER_MODEL)
    return queryset.filter(**{owner_field_name: request.user})


class OwnerFilterBackend(BaseFilterBackend):
    OWNER_FIELD_NAMES = ('user', 'owner')

    def filter_queryset(self, request, queryset, view):
        model = queryset.model
        owner_field_name = None
        for ofn in self.OWNER_FIELD_NAMES:
            if hasattr(model, ofn):
                owner_field_name = ofn
                break
        if not owner_field_name:
            raise ValueError(u'找不到owner属性, %s' % self.OWNER_FIELD_NAMES)
        # assert isinstance(getattr(model, 'user', None) or getattr(model, 'owner', None).field, settings.AUTH_USER_MODEL)
        return queryset.filter(**{owner_field_name: request.user})


def filter_with_related_field(request, queryset, related_field):
    return queryset.filter(**{related_field: request.user})


class OwnerFilterMixinDjangoFilterBackend(DjangoFilterBackend):
    OWNER_FIELD_NAMES = ('user', 'owner')
    related_field = None
    filter_callable = None

    def filter_queryset(self, request, queryset, view):
        queryset = super(OwnerFilterMixinDjangoFilterBackend, self).filter_queryset(request, queryset, view)
        if self.related_field:
            return filter_with_related_field(request, queryset, self.related_field)
        elif self.filter_callable:
            return self.filter_callable(request, queryset)
        else:
            return filter_queryset_mixin(request, queryset, self.OWNER_FIELD_NAMES)


def filter_backend(related_field, clz_name):
    return type(str(clz_name), (OwnerFilterMixinDjangoFilterBackend,), dict(related_field=related_field))


def filter_backend_hook(filter_callable, clz_name):
    return type(str(clz_name), (OwnerFilterMixinDjangoFilterBackend,), dict(filter_callable=filter_callable))


class MonthFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'以月份')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'month'

    def lookups(self, request, model_admin):
        res = [(0, _(u'全部'))]
        i = 1
        while i < 13:
            res.append((i, _(str(i) + '月')))
            i = i + 1
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        if self.value() and int(self.value()) > 0:
            return queryset.filter(month=int(self.value()))
        return qs


MonthFilter.short_description = '以月份'


class YearFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'以年份')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'year'

    def lookups(self, request, model_admin):
        year = timezone.now().year
        res = [(0, _(u'全部'))]
        i = 0
        while i < 3:
            res.append((year - i, _(str(year - i) + '年')))
            i = i + 1
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        if self.value() and int(self.value()) > 0:
            return queryset.filter(year=int(self.value()))
        return qs


MonthFilter.short_description = '以年份'


class AgentFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'以代理')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'agent_user__exact'

    def lookups(self, request, model_admin):
        res = [(0, _(u'全部'))]
        from shopping_points.models import UserAccount
        qs = UserAccount.objects.filter(flag__in=[UserAccount.UA_AGENT, UserAccount.UA_INSPECTOR])
        for inst in qs:
            res.append([inst.user.id, _('{}({})'.format(str(inst.user), inst.user.id))])
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        if self.value() and int(self.value()) > 0:
            return queryset.filter(agent_id=int(self.value()))
        return qs


class SessionFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'演出场次')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'session_filter__exact'

    def lookups(self, request, model_admin):
        res = [(0, _(u'全部'))]
        return res
        from ticket.models import SessionInfo
        qs = SessionInfo.objects.filter(is_delete=False)
        for inst in qs:
            res.append([inst.id, _(str(inst))])
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        if self.value() and int(self.value()) > 0:
            return queryset.filter(session_id=int(self.value()))
        return qs


class ShowTypeFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'以节目分类')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'show_type__exact'

    def lookups(self, request, model_admin):
        res = [(0, _(u'全部'))]
        from ticket.models import ShowType
        qs = ShowType.objects.all()
        for inst in qs:
            res.append([inst.id, _(str(inst))])
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        if self.value() and int(self.value()) > 0:
            return queryset.filter(session__show__show_type_id=int(self.value()))
        return qs


class CityFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'以城市')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'city_id'

    def lookups(self, request, model_admin):
        res = [(0, _(u'全部'))]
        from express.models import Division
        qs = Division.objects.filter(type=Division.TYPE_CITY)
        for inst in qs:
            res.append([inst.id, _(str(inst))])
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        if self.value() and int(self.value()) > 0:
            return queryset.filter(city_id=int(self.value()))
        return qs


class CardShowTypeFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'以节目分类')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'showtype'

    def lookups(self, request, model_admin):
        res = [(0, _('无'))]
        from ticket.models import ShowType
        qs = ShowType.objects.all()
        for inst in qs:
            res.append([inst.id, _(str(inst))])
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        if self.value():
            if int(self.value()) > 0:
                return queryset.filter(show_type_id=int(self.value()))
            else:
                return queryset.filter(show_type__isnull=True)
        return qs


class UserAdminTypeFilter(SimpleListFilter):
    title = _(u'搜索类型')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'useradmin_type__exact'

    def lookups(self, request, model_admin):
        res = [(1, _('用户ID')), (2, _('手机号')), (3, _('用户名')), (4, _('用户Uid'))]
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        qs = queryset
        return qs
