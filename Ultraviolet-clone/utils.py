"""
Ultraviolet Proxy - Utility Functions
"""

import base64
import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Optional


def encode_url(url: str) -> str:
    """
    Encode URL using URL-safe base64.
    
    Args:
        url: The URL to encode
        
    Returns:
        Base64 encoded string (URL-safe)
    """
    encoded = base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')
    # Remove padding for cleaner URLs
    return encoded.rstrip('=')


def decode_url(encoded: str) -> str:
    """
    Decode URL-safe base64 encoded URL.
    
    Args:
        encoded: The encoded URL string
        
    Returns:
        Decoded URL string
    """
    try:
        # Add back padding if necessary
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += '=' * padding
        return base64.urlsafe_b64decode(encoded.encode('utf-8')).decode('utf-8')
    except Exception:
        return encoded


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """
    Normalize a URL by adding protocol if missing.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL with protocol
    """
    url = url.strip()
    if not url:
        return url
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    return url


def get_base_url(url: str) -> str:
    """
    Get the base URL (scheme + netloc) from a full URL.
    
    Args:
        url: Full URL
        
    Returns:
        Base URL (e.g., https://example.com)
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def make_absolute_url(url: str, base_url: str) -> str:
    """
    Convert a relative URL to absolute.
    
    Args:
        url: Potentially relative URL
        base_url: Base URL for resolution
        
    Returns:
        Absolute URL
    """
    if not url:
        return url
    
    # Already absolute
    if url.startswith(('http://', 'https://', '//')):
        if url.startswith('//'):
            parsed_base = urlparse(base_url)
            return f"{parsed_base.scheme}:{url}"
        return url
    
    return urljoin(base_url, url)


def should_skip_url(url: str) -> bool:
    """
    Check if a URL should be skipped (not rewritten).
    
    Args:
        url: URL to check
        
    Returns:
        True if should skip, False otherwise
    """
    skip_prefixes = (
        'data:',
        'javascript:',
        'about:',
        'blob:',
        'mailto:',
        'tel:',
        '#',
    )
    return url.startswith(skip_prefixes) if url else True


def extract_urls_from_css(css: str) -> list:
    """
    Extract all URLs from CSS content.
    
    Args:
        css: CSS content
        
    Returns:
        List of URLs found
    """
    urls = []
    
    # Match url() patterns
    url_pattern = re.compile(r'url\(["\']?([^"\'()]+)["\']?\)', re.IGNORECASE)
    urls.extend(url_pattern.findall(css))
    
    # Match @import patterns
    import_pattern = re.compile(r'@import\s+["\']([^"\']+)["\']', re.IGNORECASE)
    urls.extend(import_pattern.findall(css))
    
    return urls


def get_content_type(headers: dict) -> Optional[str]:
    """
    Extract content type from headers.
    
    Args:
        headers: Response headers dictionary
        
    Returns:
        Content type string or None
    """
    content_type = headers.get('Content-Type', headers.get('content-type', ''))
    if ';' in content_type:
        content_type = content_type.split(';')[0].strip()
    return content_type.lower() if content_type else None


def is_html_content(content_type: str) -> bool:
    """Check if content type is HTML."""
    return 'text/html' in content_type.lower() if content_type else False


def is_css_content(content_type: str) -> bool:
    """Check if content type is CSS."""
    return 'text/css' in content_type.lower() if content_type else False


def is_javascript_content(content_type: str) -> bool:
    """Check if content type is JavaScript."""
    js_types = ['javascript', 'ecmascript']
    return any(t in content_type.lower() for t in js_types) if content_type else False


def is_binary_content(content_type: str) -> bool:
    """Check if content type is binary."""
    text_types = ['text/', 'application/json', 'application/javascript', 'application/xml']
    if not content_type:
        return True
    return not any(t in content_type.lower() for t in text_types)


def sanitize_headers(headers: dict, allowed_headers: list) -> dict:
    """
    Filter headers to only include allowed ones.
    
    Args:
        headers: Original headers
        allowed_headers: List of allowed header names (lowercase)
        
    Returns:
        Filtered headers dictionary
    """
    return {
        k: v for k, v in headers.items()
        if k.lower() in allowed_headers
    }
