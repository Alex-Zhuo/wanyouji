# coding:utf-8
from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 20

    def get_paginated_response_ext(self, data, ext_data=None):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
            ('ext_data', ext_data)
        ]))


class DefaultNoPagePagination(PageNumberPagination):
    """
    默认不分页, 传了page_size才分
    """
    page_size = None
    page_size_query_param = 'page_size'


class StatusCountResultsSetPagination(StandardResultsSetPagination):
    def get_paginated_response_ext(self, data, ext_data=None):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
            ('ext_data', ext_data)
        ]))


class FixPagePagination(PageNumberPagination):
    """
    默认不分页, 传了page_size才分
    """
    page_size = 10
    page_size_query_param = 'page_size'

    invalid_page_message = u'没有更多数据'
    # def paginate_queryset(self, queryset, request, view=None):
    #     pass
    def get_page_size(self, request):
        return self.page_size