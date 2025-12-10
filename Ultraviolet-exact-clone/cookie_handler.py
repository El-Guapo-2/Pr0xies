"""
Ultraviolet Python Clone - Cookie Handler
Mirrors the JavaScript cookie.js functionality

WARNING: This file handles cookies for both client and server.
"""

from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime, timezone
import json
import re


def parse_set_cookie(header: str) -> Dict[str, Any]:
    """
    Parse a Set-Cookie header into a cookie object.
    
    Args:
        header: The Set-Cookie header value
        
    Returns:
        A dictionary with cookie attributes
    """
    cookie = {
        'name': '',
        'value': '',
        'path': '/',
        'domain': '',
        'expires': None,
        'maxAge': None,
        'secure': False,
        'httpOnly': False,
        'sameSite': None
    }
    
    if not header:
        return cookie
    
    parts = header.split(';')
    
    # First part is name=value
    if parts:
        first_part = parts[0].strip()
        eq_index = first_part.find('=')
        if eq_index > 0:
            cookie['name'] = first_part[:eq_index].strip()
            cookie['value'] = first_part[eq_index + 1:].strip()
    
    # Parse attributes
    for part in parts[1:]:
        part = part.strip()
        if not part:
            continue
        
        lower_part = part.lower()
        
        if lower_part == 'secure':
            cookie['secure'] = True
        elif lower_part == 'httponly':
            cookie['httpOnly'] = True
        elif '=' in part:
            attr_name, attr_value = part.split('=', 1)
            attr_name = attr_name.strip().lower()
            attr_value = attr_value.strip()
            
            if attr_name == 'path':
                cookie['path'] = attr_value
            elif attr_name == 'domain':
                cookie['domain'] = attr_value.lstrip('.')
            elif attr_name == 'expires':
                try:
                    cookie['expires'] = attr_value
                except Exception:
                    pass
            elif attr_name == 'max-age':
                try:
                    cookie['maxAge'] = int(attr_value)
                except Exception:
                    pass
            elif attr_name == 'samesite':
                cookie['sameSite'] = attr_value.lower()
    
    return cookie


def validate_cookie(cookie: Dict[str, Any], meta: Dict[str, Any], 
                   js: bool = False) -> bool:
    """
    Validate if a cookie should be sent for the given request.
    
    Args:
        cookie: The cookie object
        meta: Request metadata with URL info
        js: Whether this is from JavaScript (affects httpOnly)
        
    Returns:
        True if the cookie is valid for this request
    """
    # Check httpOnly for JS access
    if cookie.get('httpOnly') and js:
        return False
    
    # Parse the URL from meta
    url_str = meta.get('url', '')
    if isinstance(url_str, str):
        try:
            url = urlparse(url_str)
        except Exception:
            return False
    else:
        url = url_str
    
    hostname = getattr(url, 'hostname', '') or ''
    path = getattr(url, 'path', '/') or '/'
    scheme = getattr(url, 'scheme', 'https') or 'https'
    
    # Check domain
    cookie_domain = cookie.get('domain', '').lstrip('.')
    if cookie_domain:
        if cookie_domain.startswith('.'):
            # Subdomain matching
            if not hostname.endswith(cookie_domain[1:]) and hostname != cookie_domain[1:]:
                return False
        else:
            # Exact domain match
            if hostname != cookie_domain and not hostname.endswith('.' + cookie_domain):
                return False
    
    # Check secure flag
    if cookie.get('secure') and scheme == 'http':
        return False
    
    # Check path
    cookie_path = cookie.get('path', '/')
    if not path.startswith(cookie_path):
        return False
    
    return True


def serialize_cookies(cookies: List[Dict[str, Any]], meta: Dict[str, Any], 
                     js: bool = False) -> str:
    """
    Serialize cookies into a Cookie header string.
    
    Args:
        cookies: List of cookie objects
        meta: Request metadata
        js: Whether this is for JavaScript access
        
    Returns:
        Cookie header string (name=value; name2=value2)
    """
    valid_cookies = []
    
    for cookie in cookies:
        if validate_cookie(cookie, meta, js):
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            if name:
                valid_cookies.append(f"{name}={value}")
    
    return '; '.join(valid_cookies)


def parse_cookies(cookie_header: str) -> List[Dict[str, Any]]:
    """
    Parse a Cookie header into a list of cookie objects.
    
    Args:
        cookie_header: The Cookie header value
        
    Returns:
        List of cookie dictionaries
    """
    cookies = []
    
    if not cookie_header:
        return cookies
    
    for part in cookie_header.split(';'):
        part = part.strip()
        if not part:
            continue
        
        eq_index = part.find('=')
        if eq_index > 0:
            name = part[:eq_index].strip()
            value = part[eq_index + 1:].strip()
            cookies.append({
                'name': name,
                'value': value,
                'path': '/',
                'domain': ''
            })
    
    return cookies


def rewrite_set_cookie(header: str, meta: Dict[str, Any], 
                       proxy_origin: str) -> str:
    """
    Rewrite a Set-Cookie header for the proxy.
    
    Args:
        header: The original Set-Cookie header
        meta: Request metadata
        proxy_origin: The proxy server origin
        
    Returns:
        Rewritten Set-Cookie header
    """
    cookie = parse_set_cookie(header)
    
    if not cookie['name']:
        return header
    
    # Get the original URL's domain
    url_str = meta.get('url', '')
    if isinstance(url_str, str):
        try:
            url = urlparse(url_str)
            original_domain = url.hostname or ''
        except Exception:
            original_domain = ''
    else:
        original_domain = getattr(url_str, 'hostname', '') or ''
    
    # Build the rewritten Set-Cookie
    parts = [f"{cookie['name']}={cookie['value']}"]
    
    # Set path to the proxy prefix + original path
    if cookie.get('path'):
        parts.append(f"Path={cookie['path']}")
    else:
        parts.append("Path=/")
    
    # Remove domain attribute (cookies will be set for proxy domain)
    # Don't add domain - let it default to current host
    
    if cookie.get('expires'):
        parts.append(f"Expires={cookie['expires']}")
    
    if cookie.get('maxAge') is not None:
        parts.append(f"Max-Age={cookie['maxAge']}")
    
    if cookie.get('secure'):
        parts.append("Secure")
    
    if cookie.get('httpOnly'):
        parts.append("HttpOnly")
    
    if cookie.get('sameSite'):
        parts.append(f"SameSite={cookie['sameSite']}")
    
    return '; '.join(parts)


class CookieStore:
    """
    In-memory cookie store for managing cookies.
    Simulates the IndexedDB storage used in the JS version.
    """
    
    def __init__(self):
        self._cookies: Dict[str, Dict[str, Dict[str, Any]]] = {}
    
    def get_cookies(self, origin: str) -> List[Dict[str, Any]]:
        """Get all cookies for an origin"""
        if origin not in self._cookies:
            return []
        return list(self._cookies[origin].values())
    
    def set_cookie(self, origin: str, cookie: Dict[str, Any]) -> None:
        """Set a cookie for an origin"""
        if origin not in self._cookies:
            self._cookies[origin] = {}
        
        cookie_id = f"{cookie.get('name', '')}@{cookie.get('path', '/')}@{cookie.get('domain', '')}"
        self._cookies[origin][cookie_id] = cookie
    
    def delete_cookie(self, origin: str, name: str, 
                     path: str = '/', domain: str = '') -> None:
        """Delete a cookie"""
        if origin not in self._cookies:
            return
        
        cookie_id = f"{name}@{path}@{domain}"
        self._cookies[origin].pop(cookie_id, None)
    
    def clear(self, origin: Optional[str] = None) -> None:
        """Clear cookies for an origin or all cookies"""
        if origin:
            self._cookies.pop(origin, None)
        else:
            self._cookies.clear()


# Global cookie store
_cookie_store = CookieStore()


def get_cookie_store() -> CookieStore:
    """Get the global cookie store"""
    return _cookie_store
