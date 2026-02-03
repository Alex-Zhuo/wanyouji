# coding:utf-8
import logging
from django.db import connections, models
from rest_framework.exceptions import APIException

from dj_ext.exceptions import AdminExceptionMixin, CommonExceptionMixin

logger = logging.getLogger(__name__)


class DRFExceptionMixin(CommonExceptionMixin):
    pass


class AppendDetailMixin(APIException):
    def __init__(self, detail=None, code=None):
        super(AppendDetailMixin, self).__init__(detail=(self.default_detail or '') + (detail or ''),
                                                code=(self.default_code or '') + (code or ''))

    def get_full_details(self): pass


class UserExisted(APIException):
    status_code = 420
    default_code = default_detail = u'该手机已经注册'


class ArgumentError(APIException):
    status_code = 400
    default_code = default_detail = u'参数错误'


class UnknowException(AppendDetailMixin):
    status_code = 500
    default_code = default_detail = '系统错误, 请稍后再试'


class DoNotRepeatPayment(AppendDetailMixin):
    status_code = 400
    default_code = default_detail = '请勿重复支付'


class LackArg(AppendDetailMixin):
    status_code = 400
    default_code = default_detail = '缺少参数'


class UnknownOAuthScope(AppendDetailMixin):
    status_code = 400
    default_code = default_detail = '未知的scope参数'


class SystemMPNotFound(AppendDetailMixin):
    status_code = 404
    default_code = default_detail = '公众号找不到'


class CannotGetOpenid(AppendDetailMixin):
    status_code = 500
    default_code = default_detail = '无法获取用户信息'


class CannotGetUserInfo(AppendDetailMixin):
    status_code = 500
    default_code = default_detail = '无法获取用户用户信息'


class CustomAPIException(APIException, AdminExceptionMixin, DRFExceptionMixin):
    status_code = 400
    default_code = 0

    def __init__(self, detail=None, code=None, status_code=400):
        self.status_code = status_code
        detail = detail or dict(detail=self.default_detail, msg=self.default_detail)
        super(CustomAPIException, self).__init__(code=code or self.default_code,
                                                 detail=dict(msg=detail) if isinstance(detail, str) else detail)
        self.construct(status_code=self.status_code, code=code, msg=detail, internal=detail)

    def __str__(self):
        return str(self.detail)


class PermissionNotEnoughAPIException(APIException):
    status_code = 400
    default_detail = '您没有执行该操作的权限'


class ResourceNotFound(CustomAPIException):
    status_code = 400
    default_detail = '资源找不到'


# class AdminException(CustomAPIException):
#     status = 400


def set_rollback():
    for db in connections.all():
        if db.settings_dict['ATOMIC_REQUESTS'] and db.in_atomic_block:
            db.set_rollback(True)


def exception_handler(exc, context):
    from rest_framework import exceptions
    from django.http import Http404
    from rest_framework.response import Response
    import six
    from django.utils.translation import ugettext_lazy as _

    from django.core.exceptions import PermissionDenied
    # logger.error(context)
    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        def resolve_errcode(exc):
            """
            通过exc返回codes
            :param exc:
            :return:
            """
            codes = exc.get_codes()
            if isinstance(codes, str):
                return codes
            elif isinstance(codes, dict):
                return codes.values()
            else:
                logger.error("unknow type of exc.get_code(): %s, %s" % (exc, codes))
                return 0

        if isinstance(exc.detail, (list, dict)):
            err = ','.join(exc.detail) if isinstance(exc.detail, list) else (
                    exc.detail.get('msg') or exc.detail.get('detail'))
            logger.debug('%s' % exc.detail)
            err = err or '请求错误'
            data = dict(msg=err, errcode=resolve_errcode(exc))
        else:
            data = {'msg': exc.detail, 'errcode': resolve_errcode(exc)}

        set_rollback()
        return Response(data, status=exc.status_code, headers=headers)

    elif isinstance(exc, Http404):
        msg = six.text_type(_('Not found.'))
        data = {'msg': msg}

        set_rollback()
        return Response(data, status=404)

    elif isinstance(exc, PermissionDenied):
        msg = six.text_type(_('Permission denied.'))
        data = {'msg': six.text_type(msg)}

        set_rollback()
        return Response(data, status=403)

    return None


def response_success(code=None, msg=None):
    data = dict()
    data['code'] = code if code else 200
    data['msg'] = msg if msg else '成功'
    return data


class AdminException(CustomAPIException):
    status = 400


class GoodsStockFailedException(CustomAPIException):
    default_detail = '库存不足'


class BalanceNotEnough(AppendDetailMixin):
    status_code = 400
    default_code = default_detail = '余额不足'
