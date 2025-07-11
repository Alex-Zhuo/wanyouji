# coding: utf-8
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Q


class HasParentFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'是否有上级')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'has_parent_status'

    def lookups(self, request, model_admin):
        return (
            ('has_parent', _(u'有上级')),
            ('has_no_parent', _(u'无上级')),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() == 'has_parent':
            return queryset.filter(parent__isnull=False)
        if self.value() == 'has_no_parent':
            return queryset.filter(parent__isnull=True)


class ConfigTypeFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'配置类型')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'paid_status'

    def lookups(self, request, model_admin):
        return (
            ('default', _(u'默认配置')),
            ('good', _(u'商品配置')),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() == 'default':
            return queryset.filter(good__isnull=True)
        if self.value() == 'good':
            return queryset.filter(good__isnull=False)


from django_filters.rest_framework import DjangoFilterBackend


class OwnerFilterBackend(DjangoFilterBackend):
    """
    the FilterBackend for rest_framework, which filter the list belong to the owner
    """
    owner_field_name = 'owner'

    @classmethod
    def new(cls, owner_field_name):
        """
        if your owner field name not the 'owner', use this method to new a class which use your custom field name
        :param owner_field_name:
        :return:
        """
        return type('CustomOwnerFilterBackend', (OwnerFilterBackend,), dict(owner_field_name=owner_field_name))

    def filter_queryset(self, request, queryset, view):
        qs = super(OwnerFilterBackend, self).filter_queryset(request, queryset, view)
        return qs.filter(**{self.owner_field_name: request.user})


class OwnerAndParentFilterBackend(DjangoFilterBackend):
    """
    the FilterBackend for rest_framework, which filter the list belong to the owner
    """
    owner_field_name = 'agent__user'
    parent_field_name = 'agent__parent__user'

    @classmethod
    def new(cls, owner_field_name, parent_field_name):
        """
        if your owner field name not the 'owner', use this method to new a class which use your custom field name
        :param owner_field_name:
        :param parent_field_name
        :return:
        """
        return type('CustomOwnerFilterBackend', (OwnerAndParentFilterBackend,),
                    dict(owner_field_name=owner_field_name, parent_field_name=parent_field_name))

    def filter_queryset(self, request, queryset, view):
        qs = super(OwnerAndParentFilterBackend, self).filter_queryset(request, queryset, view)
        return qs.filter(Q(**{self.owner_field_name: request.user}) | Q(**{self.parent_field_name: request.user}))


try:
    from collections import OrderedDict
    from django import forms
    from django.contrib.admin.widgets import AdminDateWidget, AdminSplitDateTime
    from rangefilter.filter import DateRangeFilter as OriginalDateRangeFilter, \
        DateTimeRangeFilter as OriginDateTimeRangeFilter
    from django.utils.translation import ugettext as _


    class DateTimeRangeFilter(OriginDateTimeRangeFilter):
        def get_template(self):
            return 'rangefilter/date_filter.html'

        def _get_form_fields(self):
            # this is here, because in parent DateRangeFilter AdminDateWidget
            # could be imported from django-suit
            return OrderedDict((
                (self.lookup_kwarg_gte, forms.SplitDateTimeField(
                    label='',
                    widget=AdminSplitDateTime(attrs={'placeholder': _('From date')}),
                    localize=True,
                    required=False
                )),
                (self.lookup_kwarg_lte, forms.SplitDateTimeField(
                    label='',
                    widget=AdminSplitDateTime(attrs={'placeholder': _('To date')}),
                    localize=True,
                    required=False
                )),
            ))

        @staticmethod
        def _get_media():
            css = [
                'style.css',
            ]
            return forms.Media(
                css={'all': ['range_filter/css/%s' % path for path in css]}
            )
except ImportError:
    pass


class DeliverAgentFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'发货人')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'deliver_agent'

    def lookups(self, request, model_admin):
        res = [(0, _(u'平台发货')), (1, _(u'代理发货'))]
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if not self.value():
            return queryset
        if self.value() == '0':
            return queryset.filter(deliver_agent__isnull=True)
        elif self.value() == '1':
            return queryset.filter(deliver_agent__isnull=False)
        return queryset


class PayerFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _(u'发放人')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'payer'

    def lookups(self, request, model_admin):
        res = [(0, _(u'平台发放')), (1, _(u'代理发放'))]
        return res

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if not self.value():
            return queryset
        if self.value() == '0':
            return queryset.filter(payer__isnull=True)
        elif self.value() == '1':
            return queryset.filter(payer__isnull=False)
        return queryset


class OperatorOrderFilterBackend(DjangoFilterBackend):

    def filter_queryset(self, request, queryset, view):
        qs = super(OperatorOrderFilterBackend, self).filter_queryset(request, queryset, view)
        return qs.filter(agent__partner=request.user.operator.partner)


class VendorUserAccountListFilter(admin.SimpleListFilter):
    title = u'是否商户'
    parameter_name = 'isvendor'

    def lookups(self, request, model_admin):
        return [(1, '是'), (0, '否')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        elif self.value() == '1':
            return queryset.filter(user__vendor__isnull=False)
        elif self.value() == '0':
            return queryset.filter(user__vendor__isnull=True)


class ParentUserAccountListFilter(admin.SimpleListFilter):
    title = u'是否上级'
    parameter_name = 'isparent'

    def lookups(self, request, model_admin):
        return [(1, '是'), (0, '否')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        elif self.value() == '1':
            return queryset.filter(user__parent__mobile=request.GET.get('q'))
        elif self.value() == '0':
            return queryset.filter(user__mobile=request.GET.get('q'))


class GoodsStockFilter(admin.SimpleListFilter):
    title = u'库存数量'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return [(1, '库存小于等于0'), (2, '库存小于等于10'), (3, '库存小于等于30')]

    def queryset(self, request, queryset):
        from django.db import models
        if not self.value():
            return queryset
        elif self.value() == '1':
            return queryset.filter(models.Q(stock__lte=0) | models.Q(spec_config__stock__lte=0))
        elif self.value() == '2':
            return queryset.filter(models.Q(stock__lte=10) | models.Q(spec_config__stock__lte=10))
        elif self.value() == '3':
            return queryset.filter(models.Q(stock__lte=30) | models.Q(spec_config__stock__lte=30))
