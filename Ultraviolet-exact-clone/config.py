"""
Ultraviolet Python Clone - Configuration
Mirrors the JavaScript uv.config.js functionality
"""

import os
from typing import Callable, Optional, List
from dataclasses import dataclass, field


@dataclass
class UVInject:
    """HTML injection configuration"""
    host: str  # Regex pattern for host matching
    inject_to: str  # 'head' or 'body'
    html: str  # HTML to inject


@dataclass
class UVConfig:
    """
    Ultraviolet configuration object.
    Mirrors the TypeScript UVConfig interface.
    """
    # URL prefix for the proxy service
    prefix: str = "/service/"
    
    # Path to static files
    bundle: str = "/uv/uv.bundle.js"
    handler: str = "/uv/uv.handler.js"
    client: str = "/uv/uv.client.js"
    config: str = "/uv/uv.config.js"
    sw: str = "/uv/uv.sw.js"
    
    # Codec type: 'xor', 'base64', 'plain', 'none'
    codec: str = "xor"
    
    # Custom encode/decode functions (optional, overrides codec)
    encode_url: Optional[Callable[[str], str]] = None
    decode_url: Optional[Callable[[str], str]] = None
    
    # HTML injection settings
    inject: List[UVInject] = field(default_factory=list)
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    
    # Bare server URL (for bare-mux compatibility)
    bare_server: str = "/bare/"
    
    # Request timeout in seconds
    timeout: int = 30
    
    # Maximum response size (0 = unlimited)
    max_response_size: int = 0
    
    # Enable/disable features
    enable_websockets: bool = True
    enable_cookies: bool = True
    enable_cache: bool = True
    
    # Blocklist patterns (regex)
    blocklist: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize encode/decode functions based on codec"""
        if self.encode_url is None or self.decode_url is None:
            from codecs_uv import get_codec
            codec = get_codec(self.codec)
            if self.encode_url is None:
                self.encode_url = codec.encode
            if self.decode_url is None:
                self.decode_url = codec.decode


# Global configuration instance
_config: Optional[UVConfig] = None


def get_config() -> UVConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = UVConfig()
    return _config


def set_config(config: UVConfig) -> None:
    """Set the global configuration instance"""
    global _config
    _config = config


def load_config_from_env() -> UVConfig:
    """Load configuration from environment variables"""
    return UVConfig(
        prefix=os.getenv("UV_PREFIX", "/service/"),
        host=os.getenv("UV_HOST", "0.0.0.0"),
        port=int(os.getenv("UV_PORT", "8080")),
        debug=os.getenv("UV_DEBUG", "false").lower() == "true",
        codec=os.getenv("UV_CODEC", "xor"),
        timeout=int(os.getenv("UV_TIMEOUT", "30")),
        enable_websockets=os.getenv("UV_WEBSOCKETS", "true").lower() == "true",
        enable_cookies=os.getenv("UV_COOKIES", "true").lower() == "true",
        enable_cache=os.getenv("UV_CACHE", "true").lower() == "true",
    )
