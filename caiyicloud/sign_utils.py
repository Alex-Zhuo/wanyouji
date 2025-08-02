# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from typing import Dict
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_private_key
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.exceptions import InvalidSignature


def deal_params(params: Dict):
    # 第一步：参数排序
    keys = sorted(params.keys())

    # 第二步：把所有参数值串在一起
    query_parts = []
    for key in keys:
        value = params.get(key, '')
        if key and value:  # 检查key和value都不为空
            query_parts.append(str(value))

    # 用&连接所有值
    sign_content = '&'.join(query_parts)
    return sign_content


def sign_top_request(params: Dict, private_key: str) -> str:
    """
    签名请求参数
    
    Args:
        params: 参数字典
        private_key: 私钥字符串
    
    Returns:
        签名字符串
    """
    sign_content = deal_params(params)

    # 第三步：使用MD5WithRSA加签
    return rsa_sign(sign_content, private_key)


def rsa_sign(content: str, private_key: str) -> str:
    try:
        # Decode the base64 encoded private key
        key_der = base64.b64decode(private_key)

        # Load the private key
        private_key = load_der_private_key(
            key_der,
            password=None,
            backend=default_backend()
        )

        # Sign the content
        signature = private_key.sign(
            content.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.MD5()  # Using MD5 as in the Java code
        )

        # Return base64 encoded signature
        return base64.b64encode(signature).decode('utf-8')

    except Exception as e:
        print(f"Error during signing: {e}")
        return ''


def do_check(params: Dict, sign: str, public_key: str) -> bool:
    """
    Verify RSA signature

    Args:
        params:
        sign: Base64 encoded signature to verify
        public_key: Base64 encoded DER public key

    Returns:
        bool: True if signature is valid, False otherwise
    """
    content = deal_params(params)
    try:
        # Decode base64 encoded public key
        key_der = base64.b64decode(public_key)

        # Load the public key
        pub_key = load_der_public_key(
            key_der
        )

        # Decode the signature
        signature = base64.b64decode(sign)

        # Verify the signature
        pub_key.verify(
            signature,
            content.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.MD5()
        )
        return True

    except InvalidSignature:
        return False
    except Exception as e:
        print(f"Verification error: {e}")
        return False
