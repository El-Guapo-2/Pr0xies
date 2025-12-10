"""
Ultraviolet Python Clone - Core Ultraviolet Class
Mirrors the JavaScript rewrite/index.js Ultraviolet class
"""

from typing import Optional, Dict, Any, Callable, List
from urllib.parse import urljoin, urlparse, quote, unquote
import re

from codecs_uv import get_codec, XORCodec
from rewrite_html import HTMLRewriter, create_html_inject, create_js_inject
from rewrite_css import CSSRewriter
from rewrite_js import JSRewriter
from cookie_handler import (
    validate_cookie, serialize_cookies, parse_set_cookie,
    get_cookie_store, CookieStore
)


class Ultraviolet:
    """
    Main Ultraviolet class that handles URL encoding/decoding and content rewriting.
    Mirrors the JavaScript Ultraviolet class from rewrite/index.js.
    """
    
    # URL patterns that should not be rewritten
    URL_REGEX = re.compile(r'^(#|about:|data:|mailto:|blob:|javascript:)')
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Ultraviolet with configuration.
        
        Args:
            config: Configuration dictionary
        """
        config = config or {}
        
        # Core settings
        self.prefix = config.get('prefix', '/service/')
        
        # URL encode/decode
        codec_name = config.get('codec', 'xor')
        codec = get_codec(codec_name)
        self.encode_url_fn = config.get('encodeUrl') or codec.encode
        self.decode_url_fn = config.get('decodeUrl') or codec.decode
        
        # Script paths
        self.bundle_script = config.get('bundle', '/uv/uv.bundle.js')
        self.handler_script = config.get('handler', '/uv/uv.handler.js')
        self.client_script = config.get('client', '/uv/uv.client.js')
        self.config_script = config.get('config', '/uv/uv.config.js')
        
        # Metadata
        self.meta = config.get('meta', {})
        self.meta.setdefault('base', None)
        self.meta.setdefault('origin', '')
        self.meta.setdefault('url', '')
        
        # Attribute prefixes
        self.master = '__uv'
        self.data_prefix = '__uv$'
        self.attribute_prefix = '__uv'
        
        # Initialize rewriters
        self.html = HTMLRewriter(self)
        self.css = CSSRewriter(self)
        self.js = JSRewriter(self)
        
        # Cookie handling
        self.cookie_store = get_cookie_store()
        
        # Attribute helpers
        self.attrs = {
            'isUrl': lambda name, tag='': self._is_url_attr(name, tag),
            'isForbidden': lambda name: name.lower() in {
                'http-equiv', 'integrity', 'sandbox', 'nonce', 'crossorigin'
            },
            'isHtml': lambda name: name.lower() == 'srcdoc',
            'isSrcset': lambda name: name.lower() in {'srcset', 'imagesrcset'},
            'isStyle': lambda name: name.lower() == 'style',
        }
        
        # Create inject functions
        self.create_html_inject = create_html_inject
        self.create_js_inject = create_js_inject
    
    def _is_url_attr(self, name: str, tag: str = '') -> bool:
        """Check if an attribute contains a URL"""
        name = name.lower()
        if tag == 'object' and name == 'data':
            return True
        return name in {
            'src', 'href', 'action', 'poster', 'background', 'ping',
            'movie', 'profile', 'data', 'formaction', 'icon', 'manifest',
            'codebase', 'cite', 'archive', 'longdesc', 'usemap'
        }
    
    def rewrite_url(self, url: str, meta: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite a URL to go through the proxy.
        
        Args:
            url: The URL to rewrite
            meta: Optional metadata for base URL resolution
            
        Returns:
            The rewritten proxy URL
        """
        meta = meta or self.meta
        
        if not url:
            return url
        
        url = str(url).strip()
        
        # Don't rewrite special URLs
        if self.URL_REGEX.match(url):
            return url
        
        # Handle javascript: URLs specially
        if url.startswith('javascript:'):
            js_code = url[len('javascript:'):]
            rewritten_js = self.js.rewrite(js_code)
            return 'javascript:' + rewritten_js
        
        # Resolve relative URLs
        try:
            base = meta.get('base') or meta.get('url') or ''
            if base:
                resolved = urljoin(str(base), url)
            else:
                resolved = url
            
            # Build proxy URL
            origin = meta.get('origin', '')
            encoded = self.encode_url_fn(resolved)
            return f"{origin}{self.prefix}{encoded}"
            
        except Exception as e:
            # On error, try to encode as-is
            origin = meta.get('origin', '')
            encoded = self.encode_url_fn(url)
            return f"{origin}{self.prefix}{encoded}"
    
    def source_url(self, url: str, meta: Optional[Dict[str, Any]] = None) -> str:
        """
        Get the original URL from a proxy URL.
        
        Args:
            url: The proxy URL
            meta: Optional metadata
            
        Returns:
            The original URL
        """
        meta = meta or self.meta
        
        if not url:
            return url
        
        # Don't process special URLs
        if self.URL_REGEX.match(url):
            return url
        
        try:
            origin = meta.get('origin', '')
            prefix = origin + self.prefix
            
            if url.startswith(prefix):
                encoded = url[len(prefix):]
                return self.decode_url_fn(encoded)
            
            return url
            
        except Exception:
            return url
    
    def rewrite_import(self, url: str, src: str, 
                       meta: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite an import URL relative to the importing script.
        
        Args:
            url: The URL being imported
            src: The URL of the importing script
            meta: Optional metadata
            
        Returns:
            The rewritten import URL
        """
        meta = meta or self.meta.copy()
        meta['base'] = src
        return self.rewrite_url(url, meta)
    
    def encode_url(self, url: str) -> str:
        """Encode a URL using the configured codec"""
        return self.encode_url_fn(url)
    
    def decode_url(self, url: str) -> str:
        """Decode a URL using the configured codec"""
        return self.decode_url_fn(url)
    
    def rewrite_html(self, html: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite HTML content.
        
        Args:
            html: The HTML to rewrite
            options: Rewrite options
            
        Returns:
            Rewritten HTML
        """
        return self.html.rewrite(html, options)
    
    def source_html(self, html: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Get source HTML from rewritten HTML.
        
        Args:
            html: The rewritten HTML
            options: Options
            
        Returns:
            Source HTML
        """
        return self.html.source(html, options)
    
    def rewrite_css(self, css: str, context: str = 'stylesheet') -> str:
        """
        Rewrite CSS content.
        
        Args:
            css: The CSS to rewrite
            context: The context ('stylesheet' or 'declarationList')
            
        Returns:
            Rewritten CSS
        """
        return self.css.rewrite(css, {'context': context})
    
    def source_css(self, css: str, context: str = 'stylesheet') -> str:
        """
        Get source CSS from rewritten CSS.
        
        Args:
            css: The rewritten CSS
            context: The context
            
        Returns:
            Source CSS
        """
        return self.css.source(css, {'context': context})
    
    def rewrite_js(self, js: str, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite JavaScript content.
        
        Args:
            js: The JavaScript to rewrite
            data: Additional context data
            
        Returns:
            Rewritten JavaScript
        """
        return self.js.rewrite(js, data)
    
    def source_js(self, js: str, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Get source JavaScript from rewritten JavaScript.
        
        Args:
            js: The rewritten JavaScript
            data: Additional context data
            
        Returns:
            Source JavaScript
        """
        return self.js.source(js, data)
    
    # Cookie methods
    def validate_cookie(self, cookie: Dict[str, Any], js: bool = False) -> bool:
        """Validate a cookie for the current request"""
        return validate_cookie(cookie, self.meta, js)
    
    def get_cookies(self) -> List[Dict[str, Any]]:
        """Get cookies for the current origin"""
        url = self.meta.get('url', '')
        if isinstance(url, str):
            try:
                parsed = urlparse(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                origin = ''
        else:
            origin = getattr(url, 'origin', '')
        
        return self.cookie_store.get_cookies(origin)
    
    def set_cookie(self, cookie_str: str) -> Dict[str, Any]:
        """Parse and store a cookie"""
        cookie = parse_set_cookie(cookie_str)
        
        url = self.meta.get('url', '')
        if isinstance(url, str):
            try:
                parsed = urlparse(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                if not cookie.get('domain'):
                    cookie['domain'] = parsed.hostname or ''
            except Exception:
                origin = ''
        else:
            origin = getattr(url, 'origin', '')
            if not cookie.get('domain'):
                cookie['domain'] = getattr(url, 'hostname', '')
        
        if not cookie.get('path'):
            cookie['path'] = '/'
        
        self.cookie_store.set_cookie(origin, cookie)
        return cookie
    
    def serialize_cookies(self, js: bool = False) -> str:
        """Serialize cookies for the current request"""
        cookies = self.get_cookies()
        return serialize_cookies(cookies, self.meta, js)


# Codec exports (matching JS static properties)
from codecs_uv import xor, base64_codec as base64, plain, none

Ultraviolet.codec = {
    'xor': xor,
    'base64': base64,
    'plain': plain,
    'none': none
}
