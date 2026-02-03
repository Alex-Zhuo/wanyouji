# coding: utf-
from collections import OrderedDict

from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.options import IS_POPUP_VAR
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db.models import BLANK_CHOICE_DASH
from functools import wraps
from django.db.models import Sum
from django.http.response import HttpResponseBase, HttpResponseRedirect
from django.utils.translation import ugettext as _, ungettext
from mall.models import User

from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import (
    FieldDoesNotExist, ImproperlyConfigured, SuspiciousOperation,
)


# award_impl = get_active_award_manager()

class RewriteChangeList(ChangeList):

    def __init__(self, request, model, list_display, list_display_links,
                 list_filter, date_hierarchy, search_fields, list_select_related,
                 list_per_page, list_max_show_all, list_editable, model_admin, sortable_by):
        super(RewriteChangeList, self).__init__(request, model, list_display, list_display_links,
                                                list_filter, date_hierarchy, search_fields, list_select_related,
                                                list_per_page, list_max_show_all, list_editable, model_admin,
                                                sortable_by)
        self.my_filter = None

    def get_queryset(self, request):
        # First, we collect all the declared list filters.
        (self.filter_specs, self.has_filters, remaining_lookup_params,
         filters_use_distinct) = self.get_filters(request)

        # Then, we let every list filter modify the queryset to its liking.
        qs = self.root_queryset
        for filter_spec in self.filter_specs:
            if hasattr(filter_spec, 'lookup_kwarg') and hasattr(filter_spec,
                                                                'lookup_val') and filter_spec.lookup_val and len(
                filter_spec.lookup_val.split(',')) > 1:
                filter_spec.lookup_kwarg = filter_spec.lookup_kwarg.replace('exact', 'in')
                filter_spec.used_parameters = dict()
                filter_spec.used_parameters[filter_spec.lookup_kwarg] = filter_spec.lookup_val.split(',')
            new_qs = filter_spec.queryset(request, qs)
            if new_qs is not None:
                qs = new_qs

        try:
            # Finally, we apply the remaining lookup parameters from the query
            # string (i.e. those that haven't already been processed by the
            # filters).
            qs = qs.filter(**remaining_lookup_params)
        except (SuspiciousOperation, ImproperlyConfigured):
            # Allow certain types of errors to be re-raised as-is so that the
            # caller can treat them in a special way.
            raise
        except Exception as e:
            # Every other error is caught with a naked except, because we don't
            # have any other way of validating lookup parameters. They might be
            # invalid if the keyword arguments are incorrect, or if the values
            # are not in the correct type, so we might get FieldError,
            # ValueError, ValidationError, or ?.
            from django.contrib.admin.options import IncorrectLookupParameters
            raise IncorrectLookupParameters(e)

        if not qs.query.select_related:
            qs = self.apply_select_related(qs)

        # Set ordering.
        ordering = self.get_ordering(request, qs)
        qs = qs.order_by(*ordering)

        # Apply search results
        qs, search_use_distinct = self.model_admin.get_search_results(request, qs, self.query)

        # Remove duplicates from results, if necessary
        if filters_use_distinct | search_use_distinct:
            return qs.distinct()
        else:
            return qs