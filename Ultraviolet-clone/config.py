"""
Ultraviolet Proxy Configuration
"""

import os

class Config:
    """Base configuration"""
    
    # Server settings
    HOST = os.environ.get('UV_HOST', '0.0.0.0')
    PORT = int(os.environ.get('UV_PORT', 8080))
    DEBUG = os.environ.get('UV_DEBUG', 'true').lower() == 'true'
    
    # Proxy settings
    PROXY_PREFIX = os.environ.get('UV_PREFIX', '/service/')
    ENCODE_URLS = True
    INJECT_SCRIPTS = True
    
    # Request settings
    REQUEST_TIMEOUT = 30
    MAX_CONTENT_SIZE = 50 * 1024 * 1024  # 50MB
    
    # User agent
    USER_AGENT = os.environ.get(
        'UV_USER_AGENT',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    
    # Headers to forward from client to target
    FORWARD_HEADERS = [
        'accept',
        'accept-language',
        'content-type',
        'range',
        'if-none-match',
        'if-modified-since',
        'cache-control',
    ]
    
    # Headers to forward from target to client
    RESPONSE_HEADERS = [
        'content-type',
        'content-length',
        'content-range',
        'accept-ranges',
        'cache-control',
        'content-language',
        'last-modified',
        'etag',
    ]
    
    # Content types to rewrite
    REWRITE_CONTENT_TYPES = [
        'text/html',
        'text/css',
        'application/javascript',
        'text/javascript',
    ]
    
    # Blocked domains (optional)
    BLOCKED_DOMAINS = []
    
    # Allowed domains (empty = all allowed)
    ALLOWED_DOMAINS = []


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


# Select configuration based on environment
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}

def get_config():
    env = os.environ.get('UV_ENV', 'default')
    return config_map.get(env, DevelopmentConfig)()
