import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


def do_check(content: str, sign: str, public_key: str) -> bool:
    """
    RSA签名验证方法 - 对应Java的doCheck方法
    
    Args:
        content: 原始内容
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
        
        # 验证签名
        pub_key.verify(
            signature,
            content.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        return True
        
    except Exception as e:
        print(f"签名验证失败: {e}")
        return False


# 使用示例
if __name__ == "__main__":
    # 示例数据（需要根据实际情况替换）
    content = "要验证的内容"
    sign = "Base64编码的签名"
    public_key = "Base64编码的公钥"
    
    # 验证签名
    result = do_check(content, sign, public_key)
    print(f"签名验证结果: {result}") 