# -*- encoding:utf-8 -*-

"""
参考 企微的WXBizMsgCrypt
"""
import hashlib
from xiaohongshu import ierror


class SHA1:
    def getSHA1(self, token, timestamp, nonce, encrypt=None):
        """用SHA1算法生成安全签名
        @param token:  票据
        @param timestamp: 时间戳
        @param encrypt: 密文
        @param nonce: 随机字符串
        @return: 安全签名
        """
        try:
            sortlist = [token, timestamp, nonce]
            if encrypt:
                sortlist.append(encrypt)
            sortlist.sort()
            sha = hashlib.sha1()
            sha.update("".join(sortlist).encode())
            return 0, sha.hexdigest()
        except Exception:
            return ierror.XHSBizMsgCrypt_ComputeSignature_Error, None
