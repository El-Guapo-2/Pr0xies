"""
Ultraviolet Proxy Clone - Python Implementation
A web proxy server that allows browsing websites through a proxy layer.
"""

from flask import Flask, request, Response, render_template, redirect, url_for, make_response
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode, parse_qs, urlunparse
import base64
import re
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app, supports_credentials=True)

# Configuration
CONFIG = {
    'prefix': '/service/',
    'encode_url': True,
    'inject_scripts': True,
}

# Session for maintaining cookies across requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})


def encode_url(url: str) -> str:
    """Encode URL using base64 for obfuscation."""
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')


def decode_url(encoded: str) -> str:
    """Decode base64 encoded URL."""
    try:
        # Add padding if necessary
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += '=' * padding
        return base64.urlsafe_b64decode(encoded.encode()).decode()
    except Exception as e:
        print(f"Decode error: {e}")
        return encoded


def rewrite_url(url: str, base_url: str) -> str:
    """Rewrite a URL to go through the proxy."""
    if not url:
        return url
    
    url = url.strip()
    
    # Skip data URLs, javascript, and anchors
    if url.startswith(('data:', 'javascript:', '#', 'about:', 'blob:', 'mailto:', 'tel:')):
        return url
    
    # Handle protocol-relative URLs
    if url.startswith('//'):
        parsed_base = urlparse(base_url)
        url = f"{parsed_base.scheme}:{url}"
    
    # Make absolute URL
    absolute_url = urljoin(base_url, url)
    
    # Encode and create proxy URL
    encoded = encode_url(absolute_url)
    return f"{CONFIG['prefix']}{encoded}"


def rewrite_css(css: str, base_url: str) -> str:
    """Rewrite URLs in CSS content."""
    # Rewrite url() references
    def replace_url(match):
        url = match.group(1).strip('\'"')
        if url.startswith('data:'):
            return match.group(0)
        rewritten = rewrite_url(url, base_url)
        return f'url("{rewritten}")'
    
    css = re.sub(r'url\(([^)]+)\)', replace_url, css)
    
    # Rewrite @import statements
    def replace_import(match):
        url = match.group(1).strip('\'"')
        rewritten = rewrite_url(url, base_url)
        return f'@import "{rewritten}"'
    
    css = re.sub(r'@import\s+["\']?([^"\';\s]+)["\']?', replace_import, css)
    
    return css


def rewrite_javascript(js: str, base_url: str) -> str:
    """Rewrite JavaScript to intercept location and other browser APIs."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    
    # Prepend UV interception code that wraps common patterns
    prefix = f'''
/* UV Proxy Injection */
(function() {{
    if (window.__uv_js_rewritten) return;
    window.__uv_js_rewritten = true;
    
    const UV_ORIGIN = "{origin}";
    const UV_URL = "{base_url}";
    const UV_HOST = "{parsed.netloc}";
    const UV_HOSTNAME = "{parsed.hostname}";
    const UV_PROTOCOL = "{parsed.scheme}:";
    
    // Store original values
    const _location = window.location;
    const _parent = window.parent;
    const _top = window.top;
    
    // Create location spoof
    window.__uv_location = {{
        get href() {{ return UV_URL; }},
        set href(v) {{ _location.href = window.__uv_encodeUrl(v); }},
        get origin() {{ return UV_ORIGIN; }},
        get host() {{ return UV_HOST; }},
        get hostname() {{ return UV_HOSTNAME; }},
        get protocol() {{ return UV_PROTOCOL; }},
        get pathname() {{ return new URL(UV_URL).pathname; }},
        get search() {{ return new URL(UV_URL).search; }},
        get hash() {{ return _location.hash; }},
        get port() {{ return new URL(UV_URL).port; }},
        assign: function(u) {{ _location.assign(window.__uv_encodeUrl(u)); }},
        replace: function(u) {{ _location.replace(window.__uv_encodeUrl(u)); }},
        reload: function(f) {{ _location.reload(f); }},
        toString: function() {{ return UV_URL; }}
    }};
    
    // Encode URL function
    window.__uv_encodeUrl = function(url) {{
        if (!url) return url;
        try {{
            const absolute = new URL(url, UV_URL).href;
            const encoded = btoa(unescape(encodeURIComponent(absolute)))
                .replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=/g, '');
            return '/service/' + encoded;
        }} catch(e) {{
            return url;
        }}
    }};
}})();
/* End UV Proxy Injection */
'''
    
    return prefix + js


def get_injection_script(base_url: str) -> str:
    """Get the client-side injection script with service worker registration."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    
    # Escape special characters in the URL for safe JavaScript embedding
    safe_url = base_url.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
    safe_origin = origin.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
    
    return f'''
<script data-proxy="true">
// UV Config - must be defined before client script
window.__uv$config = {{
    prefix: "{CONFIG['prefix']}",
    url: "{safe_url}",
    origin: "{safe_origin}"
}};
</script>
<script data-proxy="true">
(function() {{
    'use strict';
    
    const PROXY_PREFIX = "{CONFIG['prefix']}";
    const ORIGINAL_ORIGIN = "{safe_origin}";
    const ORIGINAL_URL = "{safe_url}";
    
    // Register Service Worker
    if ('serviceWorker' in navigator) {{
        navigator.serviceWorker.register('/static/sw.js', {{
            scope: '/'
        }}).then(function(registration) {{
            console.log('[UV] Service Worker registered:', registration.scope);
        }}).catch(function(error) {{
            console.error('[UV] Service Worker registration failed:', error);
        }});
    }}
    
    // URL-safe Base64 encoding
    function encodeProxyUrl(url) {{
        try {{
            if (!url) return url;
            url = String(url);
            
            // Skip special URLs
            if (url.startsWith(PROXY_PREFIX) || 
                url.startsWith('data:') || 
                url.startsWith('javascript:') ||
                url.startsWith('about:') || 
                url.startsWith('blob:') ||
                url.startsWith('mailto:') ||
                url.startsWith('tel:') ||
                url.startsWith('#')) {{
                return url;
            }}
            
            // Make absolute
            let absolute;
            try {{
                absolute = new URL(url, ORIGINAL_URL).href;
            }} catch(e) {{
                return url;
            }}
            
            // Base64 encode
            const encoded = btoa(unescape(encodeURIComponent(absolute)))
                .replace(/\\+/g, '-')
                .replace(/\\//g, '_')
                .replace(/=/g, '');
            return PROXY_PREFIX + encoded;
        }} catch(e) {{
            console.error('[UV] Encode error:', e);
            return url;
        }}
    }}
    
    // Store original functions
    const originalSetAttribute = Element.prototype.setAttribute;
    const originalGetAttribute = Element.prototype.getAttribute;
    
    // Override fetch
    const originalFetch = window.fetch;
    window.fetch = function(input, init) {{
        try {{
            if (typeof input === 'string') {{
                input = encodeProxyUrl(input);
            }} else if (input instanceof Request) {{
                input = new Request(encodeProxyUrl(input.url), input);
            }} else if (input instanceof URL) {{
                input = encodeProxyUrl(input.href);
            }}
        }} catch(e) {{}}
        return originalFetch.call(this, input, init);
    }};
    
    // Override XMLHttpRequest.open
    const originalXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...args) {{
        try {{
            url = encodeProxyUrl(url);
        }} catch(e) {{}}
        return originalXHROpen.call(this, method, url, ...args);
    }};
    
    // Override window.open
    const originalWindowOpen = window.open;
    window.open = function(url, ...args) {{
        try {{
            if (url) url = encodeProxyUrl(url);
        }} catch(e) {{}}
        return originalWindowOpen.call(this, url, ...args);
    }};
    
    // Override Image constructor
    const OriginalImage = window.Image;
    window.Image = function(width, height) {{
        const img = new OriginalImage(width, height);
        const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
        if (descriptor) {{
            Object.defineProperty(img, 'src', {{
                get: function() {{ return descriptor.get.call(this); }},
                set: function(value) {{
                    if (value && typeof value === 'string') {{
                        value = encodeProxyUrl(value);
                    }}
                    descriptor.set.call(this, value);
                }},
                configurable: true
            }});
        }}
        return img;
    }};
    window.Image.prototype = OriginalImage.prototype;
    
    // Override Worker constructor
    const OriginalWorker = window.Worker;
    if (OriginalWorker) {{
        window.Worker = function(url, options) {{
            return new OriginalWorker(encodeProxyUrl(url), options);
        }};
        window.Worker.prototype = OriginalWorker.prototype;
    }}
    
    // Override form submission
    document.addEventListener('submit', function(e) {{
        const form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        
        let action = form.getAttribute('action') || ORIGINAL_URL;
        const method = (form.method || 'GET').toUpperCase();
        
        if (method === 'GET') {{
            e.preventDefault();
            
            const formData = new FormData(form);
            const params = new URLSearchParams();
            
            for (const [key, value] of formData.entries()) {{
                if (typeof value === 'string') {{
                    params.append(key, value);
                }}
            }}
            
            let fullUrl;
            try {{
                fullUrl = new URL(action, ORIGINAL_URL);
            }} catch(err) {{
                fullUrl = new URL(ORIGINAL_URL);
                fullUrl.pathname = action;
            }}
            
            // Merge params
            for (const [key, value] of params.entries()) {{
                fullUrl.searchParams.set(key, value);
            }}
            
            window.location.href = encodeProxyUrl(fullUrl.href);
        }} else {{
            // POST - rewrite action
            const proxiedAction = encodeProxyUrl(action);
            originalSetAttribute.call(form, 'action', proxiedAction);
        }}
    }}, true);
    
    // Override click on links
    document.addEventListener('click', function(e) {{
        let target = e.target;
        while (target && target.tagName !== 'A') {{
            target = target.parentElement;
        }}
        if (!target || !target.href) return;
        
        const href = originalGetAttribute.call(target, 'href');
        if (!href || href.startsWith(PROXY_PREFIX) || href.startsWith('javascript:') || 
            href.startsWith('data:') || href.startsWith('#') || href.startsWith('mailto:')) {{
            return;
        }}
        
        e.preventDefault();
        window.location.href = encodeProxyUrl(href);
    }}, true);
    
    // Location proxy
    const createLocationProxy = function() {{
        return new Proxy({{}}, {{
            get: function(target, prop) {{
                try {{
                    const url = new URL(ORIGINAL_URL);
                    if (prop === 'href') return ORIGINAL_URL;
                    if (prop === 'origin') return ORIGINAL_ORIGIN;
                    if (prop === 'host') return url.host;
                    if (prop === 'hostname') return url.hostname;
                    if (prop === 'pathname') return url.pathname;
                    if (prop === 'search') return url.search;
                    if (prop === 'protocol') return url.protocol;
                    if (prop === 'port') return url.port;
                    if (prop === 'hash') return window.location.hash;
                    if (prop === 'assign') return function(u) {{ window.location.assign(encodeProxyUrl(u)); }};
                    if (prop === 'replace') return function(u) {{ window.location.replace(encodeProxyUrl(u)); }};
                    if (prop === 'reload') return function() {{ window.location.reload(); }};
                    if (prop === 'toString') return function() {{ return ORIGINAL_URL; }};
                }} catch(e) {{}}
                return window.location[prop];
            }},
            set: function(target, prop, value) {{
                if (prop === 'href') {{
                    window.location.href = encodeProxyUrl(value);
                    return true;
                }}
                window.location[prop] = value;
                return true;
            }}
        }});
    }};
    
    try {{
        Object.defineProperty(document, 'location', {{
            get: createLocationProxy,
            set: function(v) {{ window.location.href = encodeProxyUrl(v); }},
            configurable: true
        }});
    }} catch(e) {{}}
    
    // Override History API
    const originalPushState = History.prototype.pushState;
    const originalReplaceState = History.prototype.replaceState;
    
    History.prototype.pushState = function(state, title, url) {{
        if (url) {{
            try {{
                url = encodeProxyUrl(new URL(url, ORIGINAL_URL).href);
            }} catch(e) {{}}
        }}
        return originalPushState.call(this, state, title, url);
    }};
    
    History.prototype.replaceState = function(state, title, url) {{
        if (url) {{
            try {{
                url = encodeProxyUrl(new URL(url, ORIGINAL_URL).href);
            }} catch(e) {{}}
        }}
        return originalReplaceState.call(this, state, title, url);
    }};
    
    // Override setAttribute for URL attributes
    Element.prototype.setAttribute = function(name, value) {{
        const urlAttrs = ['src', 'href', 'action', 'data', 'poster', 'formaction'];
        if (urlAttrs.includes(name.toLowerCase()) && typeof value === 'string') {{
            if (!value.startsWith(PROXY_PREFIX) && !value.startsWith('data:') && 
                !value.startsWith('javascript:') && !value.startsWith('#') && 
                !value.startsWith('blob:') && !value.startsWith('about:')) {{
                value = encodeProxyUrl(value);
            }}
        }}
        if (name.toLowerCase() === 'srcset' && typeof value === 'string') {{
            value = value.split(',').map(function(part) {{
                part = part.trim();
                const spaceIdx = part.lastIndexOf(' ');
                if (spaceIdx > 0) {{
                    const url = part.substring(0, spaceIdx).trim();
                    const desc = part.substring(spaceIdx).trim();
                    return encodeProxyUrl(url) + ' ' + desc;
                }}
                return encodeProxyUrl(part);
            }}).join(', ');
        }}
        return originalSetAttribute.call(this, name, value);
    }};
    
    // Override document.write/writeln
    const originalWrite = document.write.bind(document);
    const originalWriteln = document.writeln.bind(document);
    
    document.write = function(...args) {{
        // Could rewrite HTML here if needed
        return originalWrite(...args);
    }};
    
    document.writeln = function(...args) {{
        return originalWriteln(...args);
    }};
    
    // Mutation Observer for dynamic elements
    const observer = new MutationObserver(function(mutations) {{
        for (const mutation of mutations) {{
            for (const node of mutation.addedNodes) {{
                if (node.nodeType === 1) {{
                    rewriteElement(node);
                }}
            }}
        }}
    }});
    
    function rewriteElement(element) {{
        const urlAttrs = ['href', 'src', 'action', 'data', 'poster', 'formaction'];
        
        for (const attr of urlAttrs) {{
            if (element.hasAttribute && element.hasAttribute(attr)) {{
                const value = originalGetAttribute.call(element, attr);
                if (value && !value.startsWith(PROXY_PREFIX) && !value.startsWith('data:') && 
                    !value.startsWith('javascript:') && !value.startsWith('#') &&
                    !value.startsWith('blob:') && !value.startsWith('about:')) {{
                    originalSetAttribute.call(element, attr, encodeProxyUrl(value));
                }}
            }}
        }}
        
        // Handle srcset
        if (element.hasAttribute && element.hasAttribute('srcset')) {{
            const srcset = originalGetAttribute.call(element, 'srcset');
            if (srcset && !srcset.includes(PROXY_PREFIX)) {{
                const parts = srcset.split(',').map(function(part) {{
                    part = part.trim();
                    const spaceIdx = part.lastIndexOf(' ');
                    if (spaceIdx > 0) {{
                        const url = part.substring(0, spaceIdx).trim();
                        const desc = part.substring(spaceIdx).trim();
                        return encodeProxyUrl(url) + ' ' + desc;
                    }}
                    return encodeProxyUrl(part);
                }});
                originalSetAttribute.call(element, 'srcset', parts.join(', '));
            }}
        }}
        
        // Handle inline styles with url()
        if (element.style && element.style.cssText) {{
            const css = element.style.cssText;
            if (css.includes('url(') && !css.includes(PROXY_PREFIX)) {{
                element.style.cssText = css.replace(/url\\((['"]?)([^'"()]+)\\1\\)/gi, function(match, quote, url) {{
                    if (url.startsWith('data:')) return match;
                    return 'url(' + quote + encodeProxyUrl(url) + quote + ')';
                }});
            }}
        }}
        
        // Process children
        if (element.querySelectorAll) {{
            const children = element.querySelectorAll('*');
            for (const child of children) {{
                rewriteElement(child);
            }}
        }}
    }}
    
    // Start observer
    function startObserver() {{
        if (document.documentElement) {{
            observer.observe(document.documentElement, {{
                childList: true,
                subtree: true
            }});
        }}
    }}
    
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', startObserver);
    }} else {{
        startObserver();
    }}
    
    // Override sendBeacon
    if (navigator.sendBeacon) {{
        const originalSendBeacon = navigator.sendBeacon.bind(navigator);
        navigator.sendBeacon = function(url, data) {{
            return originalSendBeacon(encodeProxyUrl(url), data);
        }};
    }}
    
    // Override postMessage
    const originalPostMessage = window.postMessage.bind(window);
    window.postMessage = function(message, targetOrigin, transfer) {{
        if (targetOrigin === ORIGINAL_ORIGIN) {{
            targetOrigin = window.location.origin;
        }}
        return originalPostMessage(message, targetOrigin, transfer);
    }};
    
    // Override document.domain
    try {{
        Object.defineProperty(document, 'domain', {{
            get: function() {{ return new URL(ORIGINAL_URL).hostname; }},
            set: function(v) {{}},
            configurable: true
        }});
    }} catch(e) {{}}
    
    // Override document.referrer
    try {{
        Object.defineProperty(document, 'referrer', {{
            get: function() {{ return ORIGINAL_ORIGIN + '/'; }},
            configurable: true
        }});
    }} catch(e) {{}}
    
    // Override document.URL and documentURI
    try {{
        Object.defineProperty(document, 'URL', {{
            get: function() {{ return ORIGINAL_URL; }},
            configurable: true
        }});
        Object.defineProperty(document, 'documentURI', {{
            get: function() {{ return ORIGINAL_URL; }},
            configurable: true
        }});
    }} catch(e) {{}}
    
    console.log('[UV] Proxy client initialized for:', ORIGINAL_URL);
}})();
</script>
'''


def rewrite_html(html: str, base_url: str) -> str:
    """Rewrite all URLs in HTML content to go through proxy."""
    soup = BeautifulSoup(html, 'lxml')
    
    # Remove any existing base tags that might interfere
    for base in soup.find_all('base'):
        base.decompose()
    
    # Remove reCAPTCHA and other anti-bot scripts that won't work through proxy
    recaptcha_patterns = [
        re.compile(r'recaptcha', re.I),
        re.compile(r'captcha', re.I),
        re.compile(r'grecaptcha', re.I),
        re.compile(r'hcaptcha', re.I),
        re.compile(r'challenge', re.I),
    ]
    
    # Remove reCAPTCHA script tags
    for script in soup.find_all('script'):
        src = script.get('src', '')
        text = script.string or ''
        if any(pattern.search(src) or pattern.search(text) for pattern in recaptcha_patterns):
            script.decompose()
            continue
        # Also check for google recaptcha API
        if 'www.google.com/recaptcha' in src or 'www.gstatic.com/recaptcha' in src:
            script.decompose()
            continue
    
    # Remove reCAPTCHA divs and iframes
    for element in soup.find_all(['div', 'iframe', 'span']):
        classes = element.get('class', [])
        element_id = element.get('id', '')
        src = element.get('src', '')
        
        class_str = ' '.join(classes) if isinstance(classes, list) else str(classes)
        
        if any(pattern.search(class_str) or pattern.search(element_id) or pattern.search(src) 
               for pattern in recaptcha_patterns):
            element.decompose()
    
    # Remove noscript tags that might contain captcha fallbacks
    for noscript in soup.find_all('noscript'):
        content = str(noscript)
        if any(pattern.search(content) for pattern in recaptcha_patterns):
            noscript.decompose()
    
    # Rewrite various HTML attributes containing URLs
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
        'input': ['src', 'formaction'],
        'button': ['formaction'],
        'track': ['src'],
        'area': ['href'],
        'image': ['href', 'xlink:href'],
        'use': ['href', 'xlink:href'],
    }
    
    for tag, attrs in url_attributes.items():
        for element in soup.find_all(tag):
            for attr in attrs:
                if element.has_attr(attr):
                    original = element[attr]
                    if not original:
                        continue
                    if attr in ['srcset', 'data-srcset']:
                        # Handle srcset specially
                        srcset_parts = []
                        for part in original.split(','):
                            part = part.strip()
                            if ' ' in part:
                                url, descriptor = part.rsplit(' ', 1)
                                srcset_parts.append(f"{rewrite_url(url.strip(), base_url)} {descriptor}")
                            elif part:
                                srcset_parts.append(rewrite_url(part, base_url))
                        element[attr] = ', '.join(srcset_parts)
                    else:
                        element[attr] = rewrite_url(original, base_url)
    
    # Handle meta refresh
    for meta in soup.find_all('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)}):
        content = meta.get('content', '')
        match = re.search(r'url=(.+)', content, re.I)
        if match:
            url = match.group(1).strip('\'"')
            rewritten = rewrite_url(url, base_url)
            meta['content'] = re.sub(r'url=.+', f'url={rewritten}', content, flags=re.I)
    
    # Rewrite inline styles
    for element in soup.find_all(style=True):
        element['style'] = rewrite_css(element['style'], base_url)
    
    # Rewrite style tags
    for style in soup.find_all('style'):
        if style.string:
            style.string = rewrite_css(style.string, base_url)
    
    # Inject client-side scripts for dynamic content handling
    if CONFIG['inject_scripts']:
        injection = BeautifulSoup(get_injection_script(base_url), 'lxml')
        script_tag = injection.find('script')
        if script_tag:
            if soup.head:
                soup.head.insert(0, script_tag)
            elif soup.html:
                soup.html.insert(0, script_tag)
            else:
                soup.insert(0, script_tag)
    
    return str(soup)


def proxy_request(url: str, method: str = 'GET', headers: dict = None, data=None, cookies=None):
    """Make a proxied request to the target URL."""
    try:
        # Prepare headers
        proxy_headers = dict(session.headers)
        
        # Forward relevant headers from client
        forward_headers = [
            'accept', 'accept-language', 'content-type', 'range', 
            'if-none-match', 'if-modified-since', 'cache-control',
            'x-requested-with'
        ]
        for header in forward_headers:
            if header in request.headers:
                proxy_headers[header] = request.headers[header]
        
        # Parse target URL for referer/origin
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        proxy_headers['Referer'] = url
        proxy_headers['Origin'] = origin
        proxy_headers['Host'] = parsed.netloc
        
        # Make request
        response = session.request(
            method=method,
            url=url,
            headers=proxy_headers,
            data=data,
            cookies=cookies,
            allow_redirects=False,
            timeout=30,
            verify=True
        )
        
        return response
    except requests.exceptions.RequestException as e:
        print(f"Proxy request error: {e}")
        return None


@app.route('/')
def index():
    """Render the main proxy page."""
    return render_template('index.html')


@app.route('/search', methods=['GET', 'POST'])
def search():
    """Handle search/URL submission."""
    url = request.args.get('url') or request.form.get('url', '')
    
    if not url:
        return redirect(url_for('index'))
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    encoded = encode_url(url)
    return redirect(f"{CONFIG['prefix']}{encoded}")


# Cookie storage per domain
DOMAIN_COOKIES = {}


def get_domain_key(url: str) -> str:
    """Get domain key for cookie storage."""
    parsed = urlparse(url)
    return parsed.netloc


def store_cookies_for_domain(url: str, cookies):
    """Store cookies for a specific domain."""
    domain_key = get_domain_key(url)
    if domain_key not in DOMAIN_COOKIES:
        DOMAIN_COOKIES[domain_key] = {}
    for cookie in cookies:
        DOMAIN_COOKIES[domain_key][cookie.name] = cookie.value


def get_cookies_for_domain(url: str) -> dict:
    """Get stored cookies for a domain."""
    domain_key = get_domain_key(url)
    return DOMAIN_COOKIES.get(domain_key, {})


@app.route(f"{CONFIG['prefix']}<path:encoded_url>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy(encoded_url: str):
    """Main proxy endpoint."""
    # Decode the URL
    target_url = decode_url(encoded_url)
    
    # Handle query string - it comes separately in Flask
    if request.query_string:
        qs = request.query_string.decode('utf-8')
        if '?' in target_url:
            target_url += '&' + qs
        else:
            target_url += '?' + qs
    
    if not target_url.startswith(('http://', 'https://')):
        return Response('Invalid URL', status=400)
    
    parsed_target = urlparse(target_url)
    
    # Get request data for POST/PUT
    data = None
    if request.method in ['POST', 'PUT', 'PATCH']:
        content_type = request.headers.get('Content-Type', '')
        if 'application/x-www-form-urlencoded' in content_type:
            data = urlencode(request.form.to_dict())
        elif 'multipart/form-data' in content_type:
            data = request.get_data()
        else:
            data = request.get_data()
    
    # Get domain-specific cookies
    cookies = get_cookies_for_domain(target_url)
    
    # Also include cookies from request that match the domain pattern
    domain_key = get_domain_key(target_url)
    for cookie_name, cookie_value in request.cookies.items():
        if cookie_name.startswith(f'_uv_{domain_key}_'):
            actual_name = cookie_name[len(f'_uv_{domain_key}_'):]
            cookies[actual_name] = cookie_value
        elif not cookie_name.startswith('_'):
            cookies[cookie_name] = cookie_value
    
    # Make the proxied request
    response = proxy_request(target_url, method=request.method, data=data, cookies=cookies)
    
    if response is None:
        return Response('Failed to fetch the requested resource', status=502)
    
    # Handle redirects
    if response.status_code in [301, 302, 303, 307, 308]:
        location = response.headers.get('Location')
        if location:
            new_url = urljoin(target_url, location)
            encoded = encode_url(new_url)
            return redirect(f"{CONFIG['prefix']}{encoded}", code=response.status_code)
    
    # Store cookies from response
    if response.cookies:
        store_cookies_for_domain(target_url, response.cookies)
    
    # Get content type
    content_type = response.headers.get('Content-Type', 'text/html')
    
    # Prepare response headers - explicitly remove security headers
    resp_headers = {}
    safe_headers = ['content-language', 'cache-control', 'expires', 'pragma', 'last-modified', 'etag', 'accept-ranges']
    for header in safe_headers:
        if header in response.headers:
            resp_headers[header] = response.headers[header]
    
    # Process response based on content type
    if 'text/html' in content_type:
        try:
            encoding = response.encoding or 'utf-8'
            content = response.content.decode(encoding, errors='replace')
        except:
            content = response.content.decode('utf-8', errors='replace')
        
        modified_content = rewrite_html(content, target_url)
        
        resp = make_response(modified_content, response.status_code)
        resp.headers['Content-Type'] = content_type
        # Remove security headers that break proxying
        resp.headers['X-Frame-Options'] = 'ALLOWALL'
        resp.headers['Access-Control-Allow-Origin'] = '*'
        for k, v in resp_headers.items():
            resp.headers[k] = v
        
        # Forward cookies with domain prefix for proper isolation
        domain_key = get_domain_key(target_url)
        for cookie in response.cookies:
            resp.set_cookie(
                f'_uv_{domain_key}_{cookie.name}',
                cookie.value,
                max_age=cookie.expires if cookie.expires else 86400*30,
                path='/',
                secure=False,
                httponly=False,
                samesite='Lax'
            )
        
        return resp
    
    elif 'text/css' in content_type:
        content = response.content.decode('utf-8', errors='replace')
        modified_content = rewrite_css(content, target_url)
        resp = make_response(modified_content, response.status_code)
        resp.headers['Content-Type'] = content_type
        return resp
    
    elif 'javascript' in content_type:
        # Rewrite JavaScript to intercept location/origin checks
        try:
            js_content = response.content.decode('utf-8', errors='replace')
            js_content = rewrite_javascript(js_content, target_url)
            resp = make_response(js_content, response.status_code)
        except:
            resp = make_response(response.content, response.status_code)
        resp.headers['Content-Type'] = content_type
        resp.headers['Access-Control-Allow-Origin'] = '*'
        for k, v in resp_headers.items():
            resp.headers[k] = v
        return resp
    
    elif 'application/json' in content_type:
        resp = make_response(response.content, response.status_code)
        resp.headers['Content-Type'] = content_type
        resp.headers['Access-Control-Allow-Origin'] = '*'
        for k, v in resp_headers.items():
            resp.headers[k] = v
        return resp
    
    else:
        resp = make_response(response.content, response.status_code)
        resp.headers['Content-Type'] = content_type
        if 'content-length' in response.headers:
            resp.headers['Content-Length'] = response.headers['content-length']
        for k, v in resp_headers.items():
            resp.headers[k] = v
        for cookie in response.cookies:
            resp.set_cookie(cookie.name, cookie.value, path='/')
        return resp


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return render_template('error.html', error='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('error.html', error='Internal server error'), 500


if __name__ == '__main__':
    # Create templates and static directories if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    print("=" * 50)
    print("Ultraviolet Proxy Clone - Python Edition")
    print("=" * 50)
    print(f"Server running at: http://localhost:8080")
    print(f"Proxy prefix: {CONFIG['prefix']}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)
