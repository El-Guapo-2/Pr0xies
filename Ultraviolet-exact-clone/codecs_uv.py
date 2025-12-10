"""
Ultraviolet Python Clone - URL Codecs
Mirrors the JavaScript codecs.js functionality

WARNING: This file is used by both the client and the server.
Do not use any browser or node-specific API!
"""

from typing import Callable, Protocol
from urllib.parse import quote, unquote
import base64


class Codec(Protocol):
    """Protocol for URL codecs"""
    def encode(self, s: str) -> str: ...
    def decode(self, s: str) -> str: ...


class NoneCodec:
    """No encoding - pass through"""
    @staticmethod
    def encode(s: str) -> str:
        return s if s else s
    
    @staticmethod
    def decode(s: str) -> str:
        return s if s else s


class PlainCodec:
    """Plain URL encoding using encodeURIComponent/decodeURIComponent"""
    @staticmethod
    def encode(s: str) -> str:
        if not s:
            return s
        return quote(str(s), safe='')
    
    @staticmethod
    def decode(s: str) -> str:
        if not s:
            return s
        return unquote(str(s))


class XORCodec:
    """XOR encoding - alternating character XOR with key 2"""
    @staticmethod
    def encode(s: str) -> str:
        if not s:
            return s
        s = str(s)
        result = []
        for i, char in enumerate(s):
            if i % 2:
                # XOR every other character with 2
                result.append(chr(ord(char) ^ 2))
            else:
                result.append(char)
        return quote(''.join(result), safe='')
    
    @staticmethod
    def decode(s: str) -> str:
        if not s:
            return s
        s = unquote(str(s))
        result = []
        for i, char in enumerate(s):
            if i % 2:
                # XOR every other character with 2
                result.append(chr(ord(char) ^ 2))
            else:
                result.append(char)
        return ''.join(result)


class Base64Codec:
    """Base64 encoding"""
    @staticmethod
    def encode(s: str) -> str:
        if not s:
            return s
        s = str(s)
        # First URL encode, then base64 encode
        encoded = quote(s, safe='')
        return base64.b64encode(encoded.encode('utf-8')).decode('utf-8')
    
    @staticmethod
    def decode(s: str) -> str:
        if not s:
            return s
        s = str(s)
        # First base64 decode, then URL decode
        try:
            decoded = base64.b64decode(s.encode('utf-8')).decode('utf-8')
            return unquote(decoded)
        except Exception:
            return s


# Codec registry
CODECS = {
    'none': NoneCodec(),
    'plain': PlainCodec(),
    'xor': XORCodec(),
    'base64': Base64Codec(),
}


def get_codec(name: str) -> Codec:
    """Get a codec by name"""
    return CODECS.get(name.lower(), XORCodec())


# Export codec instances for direct access
none = NoneCodec()
plain = PlainCodec()
xor = XORCodec()
base64_codec = Base64Codec()
