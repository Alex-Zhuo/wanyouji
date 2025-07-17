# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from typing import Dict, Optional

import six


class CaiyiErrorCode:
    """彩云平台错误码常量"""

    # 成功
    SUCCESS = "000000"

    # 系统级错误 (100xxx)
    REQUEST_FREQUENCY_TOO_HIGH = "100001"
    BUSINESS_EXCEPTION = "100002"
    NO_MATCHING_DELIVERY_METHOD = "100003"
    RPC_FAILURE = "100004"
    SYSTEM_PROCESSING_FAILED = "100005"
    PARAMETER_ERROR = "100006"
    API_SIGNATURE_VERIFICATION_FAILED = "100007"
    REAL_NAME_INFO_QUANTITY_MISMATCH = "100008"
    DISTRIBUTOR_ORDER_MAPPING_EXISTS = "100009"
    IP_NO_ACCESS_PERMISSION = "100164"

    # 渠道相关错误 (400xxx)
    RISK_CONTROL_QUERY_EXCEPTION = "400001"
    CHANNEL_INFO_QUERY_EXCEPTION = "400001"  # 注意：与风控查询异常使用相同错误码
    CHANNEL_ORDER_INFO_QUERY_EXCEPTION = "400002"

    # 订单相关错误 (300xxx)
    ORDER_INFO_QUERY_EXCEPTION = "300001"
    ORDER_PLACEMENT_FAILED = "300002"

    # 节目相关错误 (200xxx)
    PROGRAM_LIST_INFO_QUERY_EXCEPTION = "200001"
    PROGRAM_ID_ERROR = "200002"

    # 票价相关错误 (2002xx)
    TICKET_PRICE_INFO_QUERY_EXCEPTION = "200201"

    # 座位相关错误 (2003xx)
    SEAT_INFO_QUERY_EXCEPTION = "200301"

    # 套票相关错误 (2004xx)
    BUNDLE_TICKET_INFO_NOT_FOUND = "200401"
    BUNDLE_TICKET_BASIC_TICKET_NOT_FOUND = "200402"

    # 场次相关错误 (2001xx)
    SESSION_ID_ERROR = "200101"


# 错误码到错误消息的映射
ERROR_CODE_MESSAGES: Dict[str, str] = {
    CaiyiErrorCode.SUCCESS: "成功",
    CaiyiErrorCode.REQUEST_FREQUENCY_TOO_HIGH: "请求频率过高",
    CaiyiErrorCode.BUSINESS_EXCEPTION: "业务异常",
    CaiyiErrorCode.NO_MATCHING_DELIVERY_METHOD: "未匹配到对应的配送方式",
    CaiyiErrorCode.RPC_FAILURE: "RPC失败",
    CaiyiErrorCode.SYSTEM_PROCESSING_FAILED: "系统处理失败",
    CaiyiErrorCode.PARAMETER_ERROR: "参数错误",
    CaiyiErrorCode.API_SIGNATURE_VERIFICATION_FAILED: "API签名验证失败",
    CaiyiErrorCode.REAL_NAME_INFO_QUANTITY_MISMATCH: "实名信息数量不匹配",
    CaiyiErrorCode.DISTRIBUTOR_ORDER_MAPPING_EXISTS: "分销商订单关系映射已存在，请勿重复下单",
    CaiyiErrorCode.RISK_CONTROL_QUERY_EXCEPTION: "风控查询异常",
    CaiyiErrorCode.CHANNEL_INFO_QUERY_EXCEPTION: "渠道信息查询异常",
    CaiyiErrorCode.CHANNEL_ORDER_INFO_QUERY_EXCEPTION: "渠道订单信息查询异常",
    CaiyiErrorCode.ORDER_INFO_QUERY_EXCEPTION: "订单信息查询异常",
    CaiyiErrorCode.ORDER_PLACEMENT_FAILED: "下单失败",
    CaiyiErrorCode.PROGRAM_LIST_INFO_QUERY_EXCEPTION: "节目列表信息查询异常",
    CaiyiErrorCode.PROGRAM_ID_ERROR: "节目ID错误",
    CaiyiErrorCode.TICKET_PRICE_INFO_QUERY_EXCEPTION: "票价信息查询异常",
    CaiyiErrorCode.SEAT_INFO_QUERY_EXCEPTION: "座位信息查询异常",
    CaiyiErrorCode.BUNDLE_TICKET_INFO_NOT_FOUND: "未找到套票信息",
    CaiyiErrorCode.BUNDLE_TICKET_BASIC_TICKET_NOT_FOUND: "未找到套票对应基础票信息",
    CaiyiErrorCode.SESSION_ID_ERROR: "场次ID错误",
    CaiyiErrorCode.IP_NO_ACCESS_PERMISSION: "ip暂无访问权限",

}


def get_error_message(error_code: str) -> str:
    """根据错误码获取错误消息"""
    return ERROR_CODE_MESSAGES.get(error_code, f"未知错误码: {error_code}")


def is_success(error_code: str) -> bool:
    """判断是否为成功状态"""
    return error_code == CaiyiErrorCode.SUCCESS


def is_system_error(error_code: str) -> bool:
    """判断是否为系统级错误"""
    return error_code.startswith("100")


def is_channel_error(error_code: str) -> bool:
    """判断是否为渠道相关错误"""
    return error_code.startswith("400")


def is_order_error(error_code: str) -> bool:
    """判断是否为订单相关错误"""
    return error_code.startswith("300")


def is_program_error(error_code: str) -> bool:
    """判断是否为节目相关错误"""
    return error_code.startswith("200")


class CaiyiErrorException(Exception):
    """彩云平台错误异常基类"""

    def __init__(self, error_code: str, error_message: Optional[str] = None,
                 request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        self.error_code = error_code
        self.error_message = error_message or get_error_message(error_code)
        self.request_data = request_data
        self.response_data = response_data
        super().__init__(self.error_message)

    def __str__(self):
        return f"[{self.error_code}] {self.error_message}"

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'error_code': self.error_code,
            'error_message': self.error_message,
            'request_data': self.request_data,
            'response_data': self.response_data
        }


class CaiyiSystemException(CaiyiErrorException):
    """系统级错误异常"""
    pass


class CaiyiChannelException(CaiyiErrorException):
    """渠道相关错误异常"""
    pass


class CaiyiOrderException(CaiyiErrorException):
    """订单相关错误异常"""
    pass


class CaiyiProgramException(CaiyiErrorException):
    """节目相关错误异常"""
    pass


def create_exception_from_error_code(error_code: str, error_message=None, request_data: Optional[dict] = None,
                                     response_data: Optional[dict] = None) -> CaiyiErrorException:
    """根据错误码创建对应的异常实例"""
    if not error_message:
        error_message = get_error_message(error_code)

    if is_system_error(error_code):
        return CaiyiSystemException(error_code, error_message, request_data, response_data)
    elif is_channel_error(error_code):
        return CaiyiChannelException(error_code, error_message, request_data, response_data)
    elif is_order_error(error_code):
        return CaiyiOrderException(error_code, error_message, request_data, response_data)
    elif is_program_error(error_code):
        return CaiyiProgramException(error_code, error_message, request_data, response_data)
    else:
        return CaiyiErrorException(error_code, error_message, request_data, response_data)


# 常用错误码的便捷异常类
class CaiyiRequestFrequencyException(CaiyiSystemException):
    """请求频率过高异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.REQUEST_FREQUENCY_TOO_HIGH, request_data=request_data,
                         response_data=response_data)


class CaiyiParameterException(CaiyiSystemException):
    """参数错误异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.PARAMETER_ERROR, request_data=request_data, response_data=response_data)


class CaiyiSignatureException(CaiyiSystemException):
    """API签名验证失败异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.API_SIGNATURE_VERIFICATION_FAILED, request_data=request_data,
                         response_data=response_data)


class CaiyiOrderPlacementException(CaiyiOrderException):
    """下单失败异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.ORDER_PLACEMENT_FAILED, request_data=request_data, response_data=response_data)


class CaiyiDuplicateOrderException(CaiyiSystemException):
    """重复下单异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.DISTRIBUTOR_ORDER_MAPPING_EXISTS, request_data=request_data,
                         response_data=response_data)


class CaiyiProgramNotFoundException(CaiyiProgramException):
    """节目不存在异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.PROGRAM_ID_ERROR, request_data=request_data, response_data=response_data)


class CaiyiSessionNotFoundException(CaiyiProgramException):
    """场次不存在异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.SESSION_ID_ERROR, request_data=request_data, response_data=response_data)


class CaiyiTicketNotFoundException(CaiyiProgramException):
    """票价信息不存在异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.TICKET_PRICE_INFO_QUERY_EXCEPTION, request_data=request_data,
                         response_data=response_data)


class CaiyiSeatNotFoundException(CaiyiProgramException):
    """座位信息不存在异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.SEAT_INFO_QUERY_EXCEPTION, request_data=request_data,
                         response_data=response_data)


class CaiyiBundleTicketNotFoundException(CaiyiProgramException):
    """套票信息不存在异常"""

    def __init__(self, request_data: Optional[dict] = None, response_data: Optional[dict] = None):
        super().__init__(CaiyiErrorCode.BUNDLE_TICKET_INFO_NOT_FOUND, request_data=request_data,
                         response_data=response_data)


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


class HttpException(Exception):
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


class CaiYiCloudClientException(HttpException):
    """CaiYiCloud API client exception class"""

    def __init__(self, errcode, errmsg, client=None,
                 request=None, response=None):
        super().__init__(errcode, errmsg)
        self.client = client
        self.request = request
        self.response = response
        self.errcode = errcode
        self.errmsg = errmsg
