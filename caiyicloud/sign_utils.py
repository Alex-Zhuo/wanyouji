# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import hashlib
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import MD5
from typing import Dict, Optional
import base64


def sign_top_request(params: Dict, private_key: str) -> str:
    """
    签名请求参数
    
    Args:
        params: 参数字典
        private_key: 私钥字符串
    
    Returns:
        签名字符串
    """
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
    
    # 第三步：使用MD5WithRSA加签
    return rsa_sign(sign_content, private_key)


def rsa_sign(content: str, private_key: str) -> str:
    """
    RSA签名
    
    Args:
        content: 待签名内容
        private_key: 私钥字符串
    
    Returns:
        签名字符串（Base64编码）
    """
    try:
        # 解析私钥
        if private_key.startswith('-----BEGIN'):
            # PEM格式私钥
            key = RSA.import_key(private_key)
        else:
            # 可能是Base64编码的私钥，需要添加PEM头尾
            if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                private_key = f"-----BEGIN PRIVATE KEY-----\n{private_key}\n-----END PRIVATE KEY-----"
            key = RSA.import_key(private_key)
        
        # 计算MD5哈希
        md5_hash = MD5.new(content.encode('utf-8'))
        
        # 使用私钥签名
        signature = pkcs1_15.new(key).sign(md5_hash)
        
        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
        
    except Exception as e:
        raise ValueError(f"RSA签名失败: {e}")


