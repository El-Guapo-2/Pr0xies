"""
Ultraviolet Python Clone - HTML Rewriter
Mirrors the JavaScript html.js and rewrite.html.js functionality
"""

from typing import Optional, List, Dict, Any, Callable
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag, NavigableString, Comment
import re
import json


# Attributes that contain URLs
URL_ATTRIBUTES = {
    'src', 'href', 'action', 'poster', 'background', 'ping', 
    'movie', 'profile', 'data', 'formaction', 'icon', 'manifest',
    'codebase', 'cite', 'archive', 'longdesc', 'usemap'
}

# Attributes that contain srcset
SRCSET_ATTRIBUTES = {'srcset', 'imagesrcset'}

# Attributes that contain HTML
HTML_ATTRIBUTES = {'srcdoc'}

# Attributes that contain CSS
STYLE_ATTRIBUTES = {'style'}

# Forbidden attributes that should be prefixed
FORBIDDEN_ATTRIBUTES = {'http-equiv', 'integrity', 'sandbox', 'nonce', 'crossorigin'}

# Event handler attributes
EVENT_ATTRIBUTES = {
    'onabort', 'onafterprint', 'onbeforeprint', 'onbeforeunload', 'onblur',
    'oncanplay', 'oncanplaythrough', 'onchange', 'onclick', 'oncontextmenu',
    'oncopy', 'oncuechange', 'oncut', 'ondblclick', 'ondrag', 'ondragend',
    'ondragenter', 'ondragleave', 'ondragover', 'ondragstart', 'ondrop',
    'ondurationchange', 'onemptied', 'onended', 'onerror', 'onfocus',
    'onhashchange', 'oninput', 'oninvalid', 'onkeydown', 'onkeypress',
    'onkeyup', 'onload', 'onloadeddata', 'onloadedmetadata', 'onloadstart',
    'onmessage', 'onmousedown', 'onmousemove', 'onmouseout', 'onmouseover',
    'onmouseup', 'onmousewheel', 'onoffline', 'ononline', 'onpagehide',
    'onpageshow', 'onpaste', 'onpause', 'onplay', 'onplaying', 'onpopstate',
    'onprogress', 'onratechange', 'onreset', 'onresize', 'onscroll',
    'onsearch', 'onseeked', 'onseeking', 'onselect', 'onstalled', 'onstorage',
    'onsubmit', 'onsuspend', 'ontimeupdate', 'ontoggle', 'onunload',
    'onvolumechange', 'onwaiting', 'onwheel'
}


def is_url_attr(name: str, tag_name: str = '') -> bool:
    """Check if an attribute contains a URL"""
    if tag_name == 'object' and name == 'data':
        return True
    return name.lower() in URL_ATTRIBUTES


def is_srcset_attr(name: str) -> bool:
    """Check if an attribute contains srcset"""
    return name.lower() in SRCSET_ATTRIBUTES


def is_html_attr(name: str) -> bool:
    """Check if an attribute contains HTML"""
    return name.lower() in HTML_ATTRIBUTES


def is_style_attr(name: str) -> bool:
    """Check if an attribute contains CSS"""
    return name.lower() in STYLE_ATTRIBUTES


def is_forbidden_attr(name: str) -> bool:
    """Check if an attribute is forbidden"""
    return name.lower() in FORBIDDEN_ATTRIBUTES


def is_event_attr(name: str) -> bool:
    """Check if an attribute is an event handler"""
    return name.lower() in EVENT_ATTRIBUTES


class HTMLRewriter:
    """
    HTML rewriter that transforms URLs, attributes, and inline scripts/styles.
    Mirrors the JavaScript HTML class.
    """
    
    def __init__(self, ctx):
        """
        Initialize the HTML rewriter.
        
        Args:
            ctx: The Ultraviolet context with rewrite methods
        """
        self.ctx = ctx
        self.attr_prefix = ctx.attribute_prefix
        self.orig_prefix = f"{self.attr_prefix}-attr-"
    
    def rewrite(self, html: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite HTML content.
        
        Args:
            html: The HTML string to rewrite
            options: Rewrite options (document, injectHead, etc.)
            
        Returns:
            The rewritten HTML string
        """
        if not html:
            return html
        
        options = options or {}
        is_document = options.get('document', False)
        inject_head = options.get('injectHead', [])
        
        try:
            # Parse HTML
            if is_document:
                soup = BeautifulSoup(html, 'html5lib')
            else:
                soup = BeautifulSoup(html, 'html.parser')
            
            # Get base URL from <base> tag if present
            base_tag = soup.find('base', href=True)
            if base_tag and is_document:
                base_href = base_tag.get('href', '')
                if base_href:
                    try:
                        self.ctx.meta['base'] = urljoin(str(self.ctx.meta.get('url', '')), base_href)
                    except Exception:
                        pass
            
            # Inject head content if specified
            if inject_head and is_document:
                head = soup.find('head')
                if head:
                    self._inject_head_content(head, inject_head)
            
            # Rewrite all elements
            for element in soup.find_all(True):
                self._rewrite_element(element, options)
            
            # Return serialized HTML
            if is_document:
                return str(soup)
            else:
                # For fragments, return inner content
                if soup.body:
                    return ''.join(str(c) for c in soup.body.children)
                return str(soup)
                
        except Exception as e:
            # On error, return original HTML
            print(f"HTML rewrite error: {e}")
            return html
    
    def source(self, html: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Reverse rewrite HTML content (get original URLs).
        
        Args:
            html: The rewritten HTML string
            options: Options (document, etc.)
            
        Returns:
            The source HTML string
        """
        if not html:
            return html
        
        options = options or {}
        is_document = options.get('document', False)
        
        try:
            if is_document:
                soup = BeautifulSoup(html, 'html5lib')
            else:
                soup = BeautifulSoup(html, 'html.parser')
            
            # Restore all elements
            for element in soup.find_all(True):
                self._source_element(element, options)
            
            if is_document:
                return str(soup)
            else:
                if soup.body:
                    return ''.join(str(c) for c in soup.body.children)
                return str(soup)
                
        except Exception as e:
            print(f"HTML source error: {e}")
            return html
    
    def _rewrite_element(self, element: Tag, options: Dict[str, Any]) -> None:
        """Rewrite a single HTML element"""
        tag_name = element.name.lower() if element.name else ''
        
        # Skip our injected elements
        if element.get('__uv-script'):
            return
        
        # Store original attributes and rewrite
        attrs_to_modify = []
        for attr_name, attr_value in list(element.attrs.items()):
            if isinstance(attr_value, list):
                attr_value = ' '.join(attr_value)
            
            new_value = self._rewrite_attribute(element, tag_name, attr_name, str(attr_value), options)
            if new_value is not None:
                attrs_to_modify.append((attr_name, new_value))
        
        for attr_name, new_value in attrs_to_modify:
            element[attr_name] = new_value
        
        # Handle inline scripts
        if tag_name == 'script':
            self._rewrite_script_content(element)
        
        # Handle inline styles
        elif tag_name == 'style':
            self._rewrite_style_content(element)
    
    def _rewrite_attribute(self, element: Tag, tag_name: str, attr_name: str, 
                          attr_value: str, options: Dict[str, Any]) -> Optional[str]:
        """Rewrite a single attribute"""
        lower_name = attr_name.lower()
        
        # Handle base href specially
        if tag_name == 'base' and lower_name == 'href' and options.get('document'):
            try:
                self.ctx.meta['base'] = urljoin(str(self.ctx.meta.get('url', '')), attr_value)
            except Exception:
                pass
        
        # URL attributes
        if is_url_attr(lower_name, tag_name):
            # Store original value
            element[f"{self.orig_prefix}{attr_name}"] = attr_value
            return self.ctx.rewrite_url(attr_value)
        
        # Srcset attributes
        if is_srcset_attr(lower_name):
            element[f"{self.orig_prefix}{attr_name}"] = attr_value
            return self.wrap_srcset(attr_value)
        
        # HTML attributes (like srcdoc)
        if is_html_attr(lower_name):
            element[f"{self.orig_prefix}{attr_name}"] = attr_value
            return self.rewrite(attr_value, {
                **options,
                'document': True,
                'injectHead': options.get('injectHead', [])
            })
        
        # Style attributes
        if is_style_attr(lower_name):
            element[f"{self.orig_prefix}{attr_name}"] = attr_value
            return self.ctx.rewrite_css(attr_value, context='declarationList')
        
        # Event handler attributes
        if is_event_attr(lower_name):
            element[f"{self.orig_prefix}{attr_name}"] = attr_value
            return self.ctx.rewrite_js(attr_value)
        
        # Forbidden attributes
        if is_forbidden_attr(lower_name):
            # Move to prefixed attribute
            element[f"{self.orig_prefix}{attr_name}"] = attr_value
            del element[attr_name]
            return None
        
        return None  # No change needed
    
    def _source_element(self, element: Tag, options: Dict[str, Any]) -> None:
        """Restore original values for an element"""
        # Find and restore prefixed attributes
        attrs_to_remove = []
        attrs_to_restore = []
        
        for attr_name in list(element.attrs.keys()):
            if attr_name.startswith(self.orig_prefix):
                original_name = attr_name[len(self.orig_prefix):]
                original_value = element[attr_name]
                attrs_to_restore.append((original_name, original_value))
                attrs_to_remove.append(attr_name)
        
        for attr_name in attrs_to_remove:
            del element[attr_name]
        
        for attr_name, attr_value in attrs_to_restore:
            element[attr_name] = attr_value
    
    def _rewrite_script_content(self, element: Tag) -> None:
        """Rewrite inline script content"""
        if element.string:
            # Check for type attribute
            script_type = element.get('type', 'text/javascript')
            if not script_type or 'javascript' in script_type.lower() or script_type == 'module':
                try:
                    rewritten = self.ctx.rewrite_js(str(element.string))
                    element.string.replace_with(rewritten)
                except Exception as e:
                    print(f"Script rewrite error: {e}")
    
    def _rewrite_style_content(self, element: Tag) -> None:
        """Rewrite inline style content"""
        if element.string:
            try:
                rewritten = self.ctx.rewrite_css(str(element.string))
                element.string.replace_with(rewritten)
            except Exception as e:
                print(f"Style rewrite error: {e}")
    
    def _inject_head_content(self, head: Tag, inject_items: List[Dict[str, Any]]) -> None:
        """Inject content into the head element"""
        # Get the BeautifulSoup document (root) to use new_tag()
        # We need to traverse up to find the actual BeautifulSoup object
        soup = head
        while soup.parent:
            soup = soup.parent
        
        # Reverse the list so when we insert at position 0, the order is preserved
        # (last item in list becomes first in HTML after all insertions)
        for item in reversed(inject_items):
            tag_name = item.get('tagName', item.get('nodeName', 'script'))
            attrs = item.get('attrs', [])
            child_nodes = item.get('childNodes', [])
            
            # Create new tag
            new_tag = soup.new_tag(tag_name)
            
            # Add attributes (including marker attributes that shouldn't be skipped)
            for attr in attrs:
                name = attr.get('name', '')
                value = attr.get('value', '')
                if name:
                    new_tag[name] = value
            
            # Add content
            for child in child_nodes:
                if child.get('nodeName') == '#text':
                    new_tag.append(child.get('value', ''))
            
            # Insert at beginning of head
            head.insert(0, new_tag)
    
    def wrap_srcset(self, srcset: str) -> str:
        """Rewrite srcset attribute value"""
        if not srcset:
            return srcset
        
        parts = []
        for src in srcset.split(','):
            src = src.strip()
            if not src:
                continue
            
            src_parts = src.split()
            if src_parts:
                src_parts[0] = self.ctx.rewrite_url(src_parts[0])
            parts.append(' '.join(src_parts))
        
        return ', '.join(parts)
    
    def unwrap_srcset(self, srcset: str) -> str:
        """Get original srcset value"""
        if not srcset:
            return srcset
        
        parts = []
        for src in srcset.split(','):
            src = src.strip()
            if not src:
                continue
            
            src_parts = src.split()
            if src_parts:
                src_parts[0] = self.ctx.source_url(src_parts[0])
            parts.append(' '.join(src_parts))
        
        return ', '.join(parts)


def create_js_inject(cookies: str = "", referrer: str = "") -> str:
    """Create JavaScript injection for cookies and referrer"""
    return (
        f"self.__uv$cookies = {json.dumps(cookies)};"
        f"self.__uv$referrer = {json.dumps(referrer)};"
    )


def create_html_inject(handler_script: str, bundle_script: str, client_script: str,
                       config_script: str, cookies: str = "", referrer: str = "") -> List[Dict[str, Any]]:
    """
    Create HTML elements to inject into the head.
    Mirrors the JavaScript createHtmlInject function.
    
    Order is critical:
    1. Cookies/referrer inline script (sets globals)
    2. Bundle (defines Ultraviolet class with codecs)
    3. Config (uses Ultraviolet.codec to set __uv$config)
    4. Client (defines UVClient class)
    5. Handler (initializes everything, applies hooks)
    """
    return [
        # 1. Cookies/referrer inline script
        {
            'tagName': 'script',
            'nodeName': 'script',
            'childNodes': [
                {
                    'nodeName': '#text',
                    'value': create_js_inject(cookies, referrer)
                }
            ],
            'attrs': [
                {'name': '__uv-script', 'value': '1', 'skip': True}
            ]
        },
        # 2. Bundle (defines Ultraviolet class)
        {
            'tagName': 'script',
            'nodeName': 'script',
            'childNodes': [],
            'attrs': [
                {'name': 'src', 'value': bundle_script, 'skip': True},
                {'name': '__uv-script', 'value': '1', 'skip': True}
            ]
        },
        # 3. Config (uses Ultraviolet.codec)
        {
            'tagName': 'script',
            'nodeName': 'script',
            'childNodes': [],
            'attrs': [
                {'name': 'src', 'value': config_script, 'skip': True},
                {'name': '__uv-script', 'value': '1', 'skip': True}
            ]
        },
        # 4. Client (defines UVClient)
        {
            'tagName': 'script',
            'nodeName': 'script',
            'childNodes': [],
            'attrs': [
                {'name': 'src', 'value': client_script, 'skip': True},
                {'name': '__uv-script', 'value': '1', 'skip': True}
            ]
        },
        # 5. Handler (uses Ultraviolet and UVClient)
        {
            'tagName': 'script',
            'nodeName': 'script',
            'childNodes': [],
            'attrs': [
                {'name': 'src', 'value': handler_script, 'skip': True},
                {'name': '__uv-script', 'value': '1', 'skip': True}
            ]
        }
    ]
