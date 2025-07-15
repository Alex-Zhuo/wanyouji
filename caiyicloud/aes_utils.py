import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import binascii

class AESUtils:
    # Using ECB mode as in the Java code (note: ECB is generally less secure than other modes)
    ALGORITHM_PADDING = "AES/ECB/PKCS5Padding"
    ALGORITHM_NAME = "AES"

    @staticmethod
    def encrypt(content: str, password: bytes):
        try:
            cipher = AES.new(password, AES.MODE_ECB)
            byte_content = content.encode('utf-8')
            padded_content = pad(byte_content, AES.block_size)
            encrypted = cipher.encrypt(padded_content)
            return encrypted
        except Exception as e:
            print(f"Encryption error: {e}")


    @staticmethod
    def decrypt(content: bytes, password: bytes):
        try:
            cipher = AES.new(password, AES.MODE_ECB)
            decrypted = cipher.decrypt(content)
            unpadded = unpad(decrypted, AES.block_size)
            return unpadded
        except Exception as e:
            print(f"Decryption error: {e}")
            return None

    @staticmethod
    def parse_hex_str_to_byte(hex_str: str):
        if not hex_str:
            return None
        try:
            return binascii.unhexlify(hex_str)
        except Exception as e:
            print(f"Hex to bytes conversion error: {e}")
            return None

    @staticmethod
    def byte_array_to_hex_string(bytes_data: bytes) -> str:
        if not bytes_data:
            return ""
        try:
            return binascii.hexlify(bytes_data).decode('utf-8')
        except Exception as e:
            print(f"Bytes to hex conversion error: {e}")
            return ""

    @staticmethod
    def encode(content: str, key: bytes) -> str:
        encrypted = AESUtils.encrypt(content, key)
        return AESUtils.byte_array_to_hex_string(encrypted) if encrypted else ""

    @staticmethod
    def encode_str_key(content: str, key: str) -> str:
        byte_key = AESUtils.parse_hex_str_to_byte(key)
        return AESUtils.encode(content, byte_key) if byte_key else ""

    @staticmethod
    def decode(content: str, key: bytes) -> str:
        byte_content = AESUtils.parse_hex_str_to_byte(content)
        if not byte_content:
            return ""
        decrypted = AESUtils.decrypt(byte_content, key)
        return decrypted.decode('utf-8') if decrypted else ""

    @staticmethod
    def decode_str_key(content: str, key: str) -> str:
        byte_key = AESUtils.parse_hex_str_to_byte(key)
        byte_content = AESUtils.parse_hex_str_to_byte(content)
        if not byte_key or not byte_content:
            return ""
        decrypted = AESUtils.decrypt(byte_content, byte_key)
        return decrypted.decode('utf-8') if decrypted else ""