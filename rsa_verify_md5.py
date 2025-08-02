import base64
import hashlib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from typing import Dict, Any


def build_sign_string(params: Dict[str, Any]) -> str:
    """
    构建签名字符串
    
    Args:
        params: 需要参与签名的参数字典
    
    Returns:
        str: 按ASCII码排序并用&连接的参数字符串
    """
    # 按参数名称的ASCII码表顺序排序
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    
    # 提取参数值并用&连接
    param_values = [str(value) for _, value in sorted_params]
    sign_string = "&".join(param_values)
    
    return sign_string


def do_check_md5_rsa(content: str, sign: str, public_key: str) -> bool:
    """
    MD5WithRSA签名验证方法
    
    Args:
        content: 原始内容（UTF-8编码的字符串）
        sign: Base64编码的签名
        public_key: Base64编码的公钥
    
    Returns:
        bool: 验证结果，True表示验证成功，False表示验证失败
    """
    try:
        # 解码Base64公钥
        encoded_key = base64.b64decode(public_key)
        
        # 加载公钥
        pub_key = serialization.load_der_public_key(encoded_key)
        
        # 解码Base64签名
        signature = base64.b64decode(sign)
        
        # 使用MD5WithRSA算法验证签名
        pub_key.verify(
            signature,
            content.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.MD5()
        )
        
        return True
        
    except (ValueError, TypeError, InvalidSignature) as e:
        print(f"签名验证失败: {e}")
        return False
    except Exception as e:
        print(f"验证过程中发生错误: {e}")
        return False


def verify_api_signature(params: Dict[str, Any], sign: str, public_key: str) -> bool:
    """
    验证API请求签名
    
    Args:
        params: 需要参与签名的参数字典（路径参数除外）
        sign: Base64编码的签名
        public_key: Base64编码的公钥
    
    Returns:
        bool: 验证结果，True表示验证成功，False表示验证失败
    """
    try:
        # 构建签名字符串
        sign_string = build_sign_string(params)
        print(f"构建的签名字符串: {sign_string}")
        
        # 验证签名
        return do_check_md5_rsa(sign_string, sign, public_key)
        
    except Exception as e:
        print(f"验证API签名时发生错误: {e}")
        return False


# 使用示例
if __name__ == "__main__":
    # 示例参数
    test_params = {
        "foo": "1",
        "bar": "2", 
        "foo_bar": "3",
        "foobar": "4"
    }
    
    # 示例数据（需要根据实际情况替换）
    test_sign = "Base64编码的签名"
    test_public_key = "Base64编码的公钥"
    
    print("原始参数:")
    for key, value in test_params.items():
        print(f"  {key}: {value}")
    
    print("\n按ASCII码排序后的参数:")
    sorted_params = sorted(test_params.items(), key=lambda x: x[0])
    for key, value in sorted_params:
        print(f"  {key}: {value}")
    
    # 构建签名字符串
    sign_string = build_sign_string(test_params)
    print(f"\n构建的签名字符串: {sign_string}")
    
    # 验证签名
    result = verify_api_signature(test_params, test_sign, test_public_key)
    print(f"\n签名验证结果: {result}") 