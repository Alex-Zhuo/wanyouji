# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import six


def to_binary(value, encoding='utf-8'):
    """Convert value to binary string, default encoding is utf-8

    :param value: Value to be converted
    :param encoding: Desired encoding
    """
    if not value:
        return b''
    if isinstance(value, six.binary_type):
        return value
    if isinstance(value, six.text_type):
        return value.encode(encoding)
    return to_text(value).encode(encoding)


def to_text(value, encoding='utf-8'):
    """Convert value to unicode, default encoding is utf-8

    :param value: Value to be converted
    :param encoding: Desired encoding
    """
    if not value:
        return ''
    if isinstance(value, six.text_type):
        return value
    if isinstance(value, six.binary_type):
        return value.decode(encoding)
    return six.text_type(value)


class KShouException(Exception):
    """Base exception for wechatpy"""

    def __init__(self, errcode, errmsg):
        """
        :param errcode: Error code
        :param errmsg: Error message
        """
        self.errcode = errcode
        self.errmsg = errmsg

    def __str__(self):
        _repr = 'Error code: {code}, message: {msg}'.format(
            code=self.errcode,
            msg=self.errmsg
        )
        if six.PY2:
            return to_binary(_repr)
        else:
            return to_text(_repr)

    def __repr__(self):
        _repr = '{klass}({code}, {msg})'.format(
            klass=self.__class__.__name__,
            code=self.errcode,
            msg=self.errmsg
        )
        if six.PY2:
            return to_binary(_repr)
        else:
            return to_text(_repr)


class KShouClientException(KShouException):
    """WeChat API client exception class"""

    def __init__(self, errcode, errmsg, client=None,
                 request=None, response=None):
        super(KShouException, self).__init__(errcode, errmsg)
        self.client = client
        self.request = request
        self.response = response
        self.errcode=errcode
        self.errmsg= errmsg


class InvalidSignatureException(KShouException):
    """Invalid signature exception class"""

    def __init__(self, errcode=-40001, errmsg='Invalid signature'):
        super(InvalidSignatureException, self).__init__(errcode, errmsg)


class APILimitedException(KShouClientException):
    """WeChat API call limited exception class"""
    pass


class InvalidAppIdException(KShouClientException):
    """Invalid app_id exception class"""

    def __init__(self, errcode=-40005, errmsg='Invalid AppId'):
        super(InvalidAppIdException, self).__init__(errcode, errmsg)

class KShouPayException(KShouClientException):
    """KShou Pay API exception class"""

    def __init__(self, return_code, result_code=None, return_msg=None,
                 errcode=None, errmsg=None, client=None,
                 request=None, response=None):
        """
        :param return_code: 返回状态码
        :param result_code: 业务结果
        :param return_msg: 返回信息
        :param errcode: 错误代码
        :param errmsg: 错误代码描述
        """
        super(KShouException, self).__init__(
            errcode,
            errmsg,
            client,
            request,
            response
        )
        self.return_code = return_code
        self.result_code = result_code
        self.return_msg = return_msg

    def __str__(self):
        _str = 'Error code: {code}, message: {msg}. Pay Error code: {pay_code}, message: {pay_msg}'.format(
            code=self.return_code,
            msg=self.return_msg,
            pay_code=self.errcode,
            pay_msg=self.errmsg
        )
        if six.PY2:
            return to_binary(_str)
        else:
            return to_text(_str)

    def __repr__(self):
        _repr = '{klass}({code}, {msg}). Pay({pay_code}, {pay_msg})'.format(
            klass=self.__class__.__name__,
            code=self.return_code,
            msg=self.return_msg,
            pay_code=self.errcode,
            pay_msg=self.errmsg
        )
        if six.PY2:
            return to_binary(_repr)
        else:
            return to_text(_repr)
