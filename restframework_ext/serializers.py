# coding: utf-8

from __future__ import unicode_literals
import logging

from restframework_ext.exceptions import CustomAPIException
# coding: utf-8

logger = logging.getLogger(__name__)


class FormatExceptionMixin(object):

    @classmethod
    def run_in_check(cls, dowhat):
        if not callable(dowhat):
            raise TypeError('erno: 100')
        try:
            return dowhat()
        except Exception as e:
            if hasattr(e, 'detail'):
                detail = e.detail
                if isinstance(e.detail, dict):
                    detail = e.detail.values()[0]
                    if isinstance(detail, list):
                        detail = detail[0]
            else:
                detail = str(e)
            raise CustomAPIException(detail)

    def is_valid(self, raise_exception=False):
        try:
            return super(FormatExceptionMixin, self).is_valid(raise_exception=True)
        except Exception as e:
            if hasattr(e, 'detail'):
                detail = e.detail
                if isinstance(e.detail, dict):
                    detail = e.detail.values()[0]
                    if isinstance(detail, list):
                        detail = detail[0]
            else:
                detail = str(e) or '{}'.format(e)
            raise CustomAPIException(detail)
