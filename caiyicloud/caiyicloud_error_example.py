# -*- coding: utf-8 -*-
"""
彩云平台错误码和异常使用示例
"""

from caiyicloud.error_codes import (
    CaiyiErrorCode, get_error_message, is_success, create_exception_from_error_code,
    CaiyiRequestFrequencyException, CaiyiParameterException, CaiyiOrderPlacementException,
    CaiyiProgramNotFoundException, CaiyiSessionNotFoundException, CaiyiTicketNotFoundException,
    CaiyiDuplicateOrderException, CaiyiSignatureException
)


def example_error_code_usage():
    """示例：错误码基本使用"""
    print("=== 错误码基本使用 ===\n")
    
    # 1. 检查成功状态
    success_code = CaiyiErrorCode.SUCCESS
    print(f"成功状态检查: {is_success(success_code)}")  # True
    
    # 2. 获取错误消息
    error_code = CaiyiErrorCode.REQUEST_FREQUENCY_TOO_HIGH
    error_message = get_error_message(error_code)
    print(f"错误码 {error_code}: {error_message}")
    
    # 3. 遍历所有错误码
    print("\n所有错误码列表:")
    for code, message in {
        CaiyiErrorCode.SUCCESS: "成功",
        CaiyiErrorCode.REQUEST_FREQUENCY_TOO_HIGH: "请求频率过高",
        CaiyiErrorCode.PARAMETER_ERROR: "参数错误",
        CaiyiErrorCode.ORDER_PLACEMENT_FAILED: "下单失败",
        CaiyiErrorCode.PROGRAM_ID_ERROR: "节目ID错误",
        CaiyiErrorCode.SESSION_ID_ERROR: "场次ID错误",
        CaiyiErrorCode.TICKET_PRICE_INFO_QUERY_EXCEPTION: "票价信息查询异常",
        CaiyiErrorCode.DISTRIBUTOR_ORDER_MAPPING_EXISTS: "分销商订单关系映射已存在，请勿重复下单"
    }.items():
        print(f"  {code}: {message}")


def example_exception_usage():
    """示例：异常处理使用"""
    print("\n=== 异常处理使用 ===\n")
    
    # 模拟API响应数据
    api_response = {
        "code": "100001",
        "message": "请求频率过高",
        "data": None
    }
    
    # 1. 根据错误码创建异常
    try:
        error_code = api_response["code"]
        if not is_success(error_code):
            exception = create_exception_from_error_code(
                error_code, 
                request_data={"test": "data"}, 
                response_data=api_response
            )
            raise exception
    except Exception as e:
        print(f"捕获异常: {e}")
        print(f"异常类型: {type(e).__name__}")
        print(f"异常详情: {e.to_dict()}")
    
    print()
    
    # 2. 使用具体的异常类
    try:
        # 模拟参数错误
        raise CaiyiParameterException(
            request_data={"invalid_param": "value"},
            response_data={"code": "100006", "message": "参数错误"}
        )
    except CaiyiParameterException as e:
        print(f"参数错误异常: {e}")
        print(f"请求数据: {e.request_data}")
        print(f"响应数据: {e.response_data}")
    
    print()
    
    # 3. 模拟订单创建失败
    try:
        raise CaiyiOrderPlacementException(
            request_data={
                "program_id": "12345",
                "session_id": "67890",
                "ticket_count": 2
            },
            response_data={"code": "300002", "message": "下单失败"}
        )
    except CaiyiOrderPlacementException as e:
        print(f"下单失败异常: {e}")
        print(f"错误码: {e.error_code}")
        print(f"错误消息: {e.error_message}")


def example_error_handling_in_api():
    """示例：在API调用中的错误处理"""
    print("\n=== API调用中的错误处理 ===\n")
    
    def mock_api_call():
        """模拟API调用"""
        # 模拟不同的错误情况
        import random
        error_codes = [
            CaiyiErrorCode.SUCCESS,
            CaiyiErrorCode.REQUEST_FREQUENCY_TOO_HIGH,
            CaiyiErrorCode.PARAMETER_ERROR,
            CaiyiErrorCode.ORDER_PLACEMENT_FAILED,
            CaiyiErrorCode.PROGRAM_ID_ERROR,
            CaiyiErrorCode.DISTRIBUTOR_ORDER_MAPPING_EXISTS
        ]
        
        return {
            "code": random.choice(error_codes),
            "message": "模拟响应",
            "data": {"order_id": "123456"} if random.choice(error_codes) == CaiyiErrorCode.SUCCESS else None
        }
    
    # 模拟多次API调用
    for i in range(5):
        print(f"API调用 {i+1}:")
        response = mock_api_call()
        error_code = response["code"]
        
        try:
            if is_success(error_code):
                print(f"  ✓ 成功: {response['data']}")
            else:
                # 根据错误码创建对应的异常
                exception = create_exception_from_error_code(error_code, response_data=response)
                
                # 根据异常类型进行不同处理
                if isinstance(exception, CaiyiRequestFrequencyException):
                    print(f"  ⚠ 请求频率过高，需要等待重试")
                elif isinstance(exception, CaiyiParameterException):
                    print(f"  ✗ 参数错误，请检查请求参数")
                elif isinstance(exception, CaiyiOrderPlacementException):
                    print(f"  ✗ 下单失败，请稍后重试")
                elif isinstance(exception, CaiyiProgramNotFoundException):
                    print(f"  ✗ 节目不存在，请检查节目ID")
                elif isinstance(exception, CaiyiDuplicateOrderException):
                    print(f"  ✗ 重复下单，请勿重复提交")
                else:
                    print(f"  ✗ 其他错误: {exception}")
                    
        except Exception as e:
            print(f"  ✗ 异常处理错误: {e}")
        
        print()


def example_custom_error_handling():
    """示例：自定义错误处理"""
    print("\n=== 自定义错误处理 ===\n")
    
    class CaiyiAPIHandler:
        """彩云平台API处理器"""
        
        def __init__(self):
            self.retry_count = 0
            self.max_retries = 3
        
        def handle_response(self, response: dict):
            """处理API响应"""
            error_code = response.get("code")
            
            if is_success(error_code):
                return response.get("data")
            
            # 根据错误码进行不同处理
            if error_code == CaiyiErrorCode.REQUEST_FREQUENCY_TOO_HIGH:
                return self._handle_frequency_limit(response)
            elif error_code == CaiyiErrorCode.PARAMETER_ERROR:
                return self._handle_parameter_error(response)
            elif error_code == CaiyiErrorCode.ORDER_PLACEMENT_FAILED:
                return self._handle_order_failure(response)
            elif error_code == CaiyiErrorCode.DISTRIBUTOR_ORDER_MAPPING_EXISTS:
                return self._handle_duplicate_order(response)
            else:
                return self._handle_unknown_error(response)
        
        def _handle_frequency_limit(self, response: dict):
            """处理请求频率限制"""
            print("检测到请求频率限制，等待重试...")
            import time
            time.sleep(2 ** self.retry_count)  # 指数退避
            self.retry_count += 1
            return None
        
        def _handle_parameter_error(self, response: dict):
            """处理参数错误"""
            print("检测到参数错误，请检查请求参数")
            raise CaiyiParameterException(response_data=response)
        
        def _handle_order_failure(self, response: dict):
            """处理下单失败"""
            print("下单失败，可能是库存不足或系统繁忙")
            raise CaiyiOrderPlacementException(response_data=response)
        
        def _handle_duplicate_order(self, response: dict):
            """处理重复下单"""
            print("检测到重复下单，请检查订单状态")
            raise CaiyiDuplicateOrderException(response_data=response)
        
        def _handle_unknown_error(self, response: dict):
            """处理未知错误"""
            error_code = response.get("code")
            print(f"未知错误: {error_code}")
            exception = create_exception_from_error_code(error_code, response_data=response)
            raise exception
    
    # 使用示例
    handler = CaiyiAPIHandler()
    
    # 模拟不同的响应
    test_responses = [
        {"code": "000000", "data": {"order_id": "123"}},
        {"code": "100001", "message": "请求频率过高"},
        {"code": "100006", "message": "参数错误"},
        {"code": "300002", "message": "下单失败"},
        {"code": "100009", "message": "重复下单"}
    ]
    
    for response in test_responses:
        try:
            result = handler.handle_response(response)
            if result:
                print(f"处理成功: {result}")
        except Exception as e:
            print(f"处理失败: {e}")
        print()


def main():
    """主函数"""
    print("彩云平台错误码和异常处理示例\n")
    print("=" * 50)
    
    example_error_code_usage()
    example_exception_usage()
    example_error_handling_in_api()
    example_custom_error_handling()
    
    print("=" * 50)
    print("示例完成！")


if __name__ == "__main__":
    main() 