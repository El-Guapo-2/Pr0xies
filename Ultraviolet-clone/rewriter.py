"""
Ultraviolet Proxy - Content Rewriting Module
Handles URL rewriting for HTML, CSS, and JavaScript content.
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import encode_url, should_skip_url


class ContentRewriter:
    """Handles content rewriting for proxied content."""
    
    def __init__(self, prefix: str = '/service/'):
        self.prefix = prefix
    
    def rewrite_url(self, url: str, base_url: str) -> str:
        """
        Rewrite a single URL to go through the proxy.
        
        Args:
            url: Original URL
            base_url: Base URL for resolving relative URLs
            
        Returns:
            Rewritten proxy URL
        """
        if not url or should_skip_url(url):
            return url
        
        # Make absolute URL
        absolute_url = urljoin(base_url, url)
        
        # Encode and create proxy URL
        encoded = encode_url(absolute_url)
        return f"{self.prefix}{encoded}"
    
    def rewrite_srcset(self, srcset: str, base_url: str) -> str:
        """
        Rewrite srcset attribute value.
        
        Args:
            srcset: Original srcset value
            base_url: Base URL for resolving relative URLs
            
        Returns:
            Rewritten srcset value
        """
        parts = []
        for item in srcset.split(','):
            item = item.strip()
            if not item:
                continue
            
            if ' ' in item:
                url, descriptor = item.rsplit(' ', 1)
                rewritten_url = self.rewrite_url(url.strip(), base_url)
                parts.append(f"{rewritten_url} {descriptor}")
            else:
                parts.append(self.rewrite_url(item, base_url))
        
        return ', '.join(parts)
    
    def rewrite_css(self, css: str, base_url: str) -> str:
        """
        Rewrite URLs in CSS content.
        
        Args:
            css: CSS content
            base_url: Base URL for resolving relative URLs
            
        Returns:
            CSS with rewritten URLs
        """
        # Rewrite url() references
        def replace_url(match):
            url = match.group(1).strip('\'"')
            rewritten = self.rewrite_url(url, base_url)
            return f'url("{rewritten}")'
        
        css = re.sub(r'url\(([^)]+)\)', replace_url, css)
        
        # Rewrite @import statements
        def replace_import(match):
            url = match.group(1).strip('\'"')
            rewritten = self.rewrite_url(url, base_url)
            return f'@import "{rewritten}"'
        
        css = re.sub(r'@import\s+["\']?([^"\';\s]+)["\']?', replace_import, css)
        
        return css
    
    def rewrite_html(self, html: str, base_url: str, inject_scripts: bool = True) -> str:
        """
        Rewrite all URLs in HTML content.
        
        Args:
            html: HTML content
            base_url: Base URL for resolving relative URLs
            inject_scripts: Whether to inject client-side proxy scripts
            
        Returns:
            HTML with rewritten URLs
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # URL attributes for different HTML elements
        url_attributes = {
            'a': ['href'],
            'link': ['href'],
            'script': ['src'],
            'img': ['src', 'srcset', 'data-src', 'data-srcset'],
            'video': ['src', 'poster'],
            'audio': ['src'],
            'source': ['src', 'srcset'],
            'iframe': ['src'],
            'embed': ['src'],
            'object': ['data'],
            'form': ['action'],
            'input': ['src'],
            'track': ['src'],
            'area': ['href'],
            'meta': ['content'],  # For refresh redirects
        }
        
        # Rewrite URL attributes
        for tag_name, attrs in url_attributes.items():
            for element in soup.find_all(tag_name):
                for attr in attrs:
                    if not element.has_attr(attr):
                        continue
                    
                    original = element[attr]
                    
                    # Special handling for meta refresh
                    if tag_name == 'meta' and attr == 'content':
                        http_equiv = element.get('http-equiv', '').lower()
                        if http_equiv == 'refresh' and 'url=' in original.lower():
                            # Parse and rewrite the URL in refresh content
                            match = re.search(r'url=(.+)', original, re.IGNORECASE)
                            if match:
                                url = match.group(1).strip('\'"')
                                rewritten = self.rewrite_url(url, base_url)
                                element[attr] = re.sub(
                                    r'url=.+',
                                    f'url={rewritten}',
                                    original,
                                    flags=re.IGNORECASE
                                )
                        continue
                    
                    # Handle srcset specially
                    if attr in ['srcset', 'data-srcset']:
                        element[attr] = self.rewrite_srcset(original, base_url)
                    else:
                        element[attr] = self.rewrite_url(original, base_url)
        
        # Rewrite inline styles
        for element in soup.find_all(style=True):
            element['style'] = self.rewrite_css(element['style'], base_url)
        
        # Rewrite style tags
        for style in soup.find_all('style'):
            if style.string:
                style.string = self.rewrite_css(style.string, base_url)
        
        # Inject client-side scripts for dynamic content handling
        if inject_scripts:
            self._inject_client_scripts(soup)
        
        return str(soup)
    
    def _inject_client_scripts(self, soup):
        """Inject client-side scripts for handling dynamic content."""
        script = soup.new_tag('script')
        script.string = f'''
        (function() {{
            'use strict';
            
            const PROXY_PREFIX = "{self.prefix}";
            const BASE_URI = document.baseURI;
            
            // URL-safe Base64 encoding
            function encodeProxyUrl(url) {{
                try {{
                    const encoded = btoa(unescape(encodeURIComponent(url)))
                        .replace(/\\+/g, '-')
                        .replace(/\\//g, '_')
                        .replace(/=/g, '');
                    return PROXY_PREFIX + encoded;
                }} catch(e) {{
                    console.error('[UV] Encode error:', e);
                    return url;
                }}
            }}
            
            // Resolve and encode URL
            function resolveAndEncode(url) {{
                if (!url || url.startsWith(PROXY_PREFIX) || 
                    url.startsWith('data:') || url.startsWith('javascript:') ||
                    url.startsWith('about:') || url.startsWith('blob:') ||
                    url.startsWith('#')) {{
                    return url;
                }}
                try {{
                    const absolute = new URL(url, BASE_URI).href;
                    return encodeProxyUrl(absolute);
                }} catch(e) {{
                    return url;
                }}
            }}
            
            // Override fetch
            const originalFetch = window.fetch;
            window.fetch = function(input, init) {{
                if (typeof input === 'string') {{
                    input = resolveAndEncode(input);
                }} else if (input instanceof Request) {{
                    input = new Request(resolveAndEncode(input.url), input);
                }}
                return originalFetch.call(this, input, init);
            }};
            
            // Override XMLHttpRequest.open
            const originalXHROpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url, ...args) {{
                return originalXHROpen.call(this, method, resolveAndEncode(url), ...args);
            }};
            
            // Override window.open
            const originalWindowOpen = window.open;
            window.open = function(url, ...args) {{
                return originalWindowOpen.call(this, resolveAndEncode(url), ...args);
            }};
            
            // Override History API
            const originalPushState = History.prototype.pushState;
            const originalReplaceState = History.prototype.replaceState;
            
            History.prototype.pushState = function(state, title, url) {{
                if (url) url = resolveAndEncode(url);
                return originalPushState.call(this, state, title, url);
            }};
            
            History.prototype.replaceState = function(state, title, url) {{
                if (url) url = resolveAndEncode(url);
                return originalReplaceState.call(this, state, title, url);
            }};
            
            // Override document.write/writeln
            const originalWrite = document.write;
            const originalWriteln = document.writeln;
            
            // Observer for dynamically added elements
            const observer = new MutationObserver(function(mutations) {{
                mutations.forEach(function(mutation) {{
                    mutation.addedNodes.forEach(function(node) {{
                        if (node.nodeType === 1) {{
                            rewriteElement(node);
                        }}
                    }});
                }});
            }});
            
            function rewriteElement(element) {{
                const urlAttrs = ['href', 'src', 'action', 'data', 'poster'];
                urlAttrs.forEach(function(attr) {{
                    if (element.hasAttribute && element.hasAttribute(attr)) {{
                        const original = element.getAttribute(attr);
                        const rewritten = resolveAndEncode(original);
                        if (original !== rewritten) {{
                            element.setAttribute(attr, rewritten);
                        }}
                    }}
                }});
                
                // Recursively handle children
                if (element.querySelectorAll) {{
                    element.querySelectorAll('[href], [src], [action], [data], [poster]').forEach(rewriteElement);
                }}
            }}
            
            // Start observing
            observer.observe(document.documentElement, {{
                childList: true,
                subtree: true
            }});
            
            console.log('[Ultraviolet Clone] Proxy scripts loaded');
        }})();
        '''
        
        # Insert at the beginning of head (or html if no head)
        if soup.head:
            soup.head.insert(0, script)
        elif soup.html:
            soup.html.insert(0, script)
        else:
            soup.insert(0, script)


# Create a default rewriter instance
default_rewriter = ContentRewriter()
