/**
 * Ultraviolet Client - Injected into proxied pages
 * Handles client-side URL rewriting and API interception
 */

(function() {
    'use strict';
    
    // Configuration passed from server
    const CONFIG = window.__uv$config || {};
    const PROXY_PREFIX = CONFIG.prefix || '/service/';
    const ORIGINAL_URL = CONFIG.url || '';
    const ORIGINAL_ORIGIN = CONFIG.origin || '';
    
    if (!ORIGINAL_URL) {
        console.error('[UV] No original URL configured');
        return;
    }
    
    console.log('[UV] Initializing client for:', ORIGINAL_URL);
    
    /**
     * URL-safe Base64 encoding
     */
    function encodeUrl(url) {
        try {
            const encoded = btoa(unescape(encodeURIComponent(url)))
                .replace(/\+/g, '-')
                .replace(/\//g, '_')
                .replace(/=/g, '');
            return PROXY_PREFIX + encoded;
        } catch (e) {
            console.error('[UV] Encode error:', e);
            return url;
        }
    }
    
    /**
     * Check if URL should be proxied
     */
    function shouldProxy(url) {
        if (!url || typeof url !== 'string') return false;
        
        const skipPrefixes = [
            'data:', 'blob:', 'javascript:', 'about:', 'mailto:', 'tel:', '#',
            PROXY_PREFIX
        ];
        
        return !skipPrefixes.some(prefix => url.startsWith(prefix));
    }
    
    /**
     * Resolve and encode URL
     */
    function resolveAndEncode(url, base = ORIGINAL_URL) {
        if (!shouldProxy(url)) return url;
        
        try {
            const absolute = new URL(url, base).href;
            return encodeUrl(absolute);
        } catch (e) {
            return url;
        }
    }
    
    // ==================== FETCH OVERRIDE ====================
    
    const originalFetch = window.fetch;
    window.fetch = function(input, init = {}) {
        try {
            let url;
            if (typeof input === 'string') {
                url = resolveAndEncode(input);
            } else if (input instanceof URL) {
                url = resolveAndEncode(input.href);
            } else if (input instanceof Request) {
                url = resolveAndEncode(input.url);
                input = new Request(url, input);
                return originalFetch.call(this, input, init);
            }
            
            if (url) {
                return originalFetch.call(this, url, init);
            }
        } catch (e) {
            console.error('[UV] Fetch override error:', e);
        }
        return originalFetch.call(this, input, init);
    };
    
    // ==================== XMLHttpRequest OVERRIDE ====================
    
    const originalXHROpen = XMLHttpRequest.prototype.open;
    const originalXHRSend = XMLHttpRequest.prototype.send;
    
    XMLHttpRequest.prototype.open = function(method, url, ...args) {
        this._uvUrl = url;
        const proxiedUrl = resolveAndEncode(url);
        return originalXHROpen.call(this, method, proxiedUrl, ...args);
    };
    
    // ==================== WebSocket OVERRIDE ====================
    
    const OriginalWebSocket = window.WebSocket;
    window.WebSocket = function(url, protocols) {
        // WebSocket proxying requires a WebSocket proxy server
        // For now, try to connect directly with modified URL
        try {
            const wsUrl = new URL(url, ORIGINAL_URL);
            // Convert to our proxy WebSocket endpoint if we had one
            // For now, just use original
            return new OriginalWebSocket(wsUrl.href, protocols);
        } catch (e) {
            return new OriginalWebSocket(url, protocols);
        }
    };
    window.WebSocket.prototype = OriginalWebSocket.prototype;
    window.WebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
    window.WebSocket.OPEN = OriginalWebSocket.OPEN;
    window.WebSocket.CLOSING = OriginalWebSocket.CLOSING;
    window.WebSocket.CLOSED = OriginalWebSocket.CLOSED;
    
    // ==================== Worker OVERRIDE ====================
    
    const OriginalWorker = window.Worker;
    window.Worker = function(url, options) {
        const proxiedUrl = resolveAndEncode(url);
        return new OriginalWorker(proxiedUrl, options);
    };
    window.Worker.prototype = OriginalWorker.prototype;
    
    const OriginalSharedWorker = window.SharedWorker;
    if (OriginalSharedWorker) {
        window.SharedWorker = function(url, options) {
            const proxiedUrl = resolveAndEncode(url);
            return new OriginalSharedWorker(proxiedUrl, options);
        };
        window.SharedWorker.prototype = OriginalSharedWorker.prototype;
    }
    
    // ==================== window.open OVERRIDE ====================
    
    const originalWindowOpen = window.open;
    window.open = function(url, target, features) {
        if (url) {
            url = resolveAndEncode(url);
        }
        return originalWindowOpen.call(this, url, target, features);
    };
    
    // ==================== LOCATION OVERRIDE ====================
    
    // Create a proxy for location-like behavior
    const locationHandler = {
        get href() { return ORIGINAL_URL; },
        set href(value) { window.location.href = resolveAndEncode(value); },
        
        get origin() { return ORIGINAL_ORIGIN; },
        get protocol() { return new URL(ORIGINAL_URL).protocol; },
        get host() { return new URL(ORIGINAL_URL).host; },
        get hostname() { return new URL(ORIGINAL_URL).hostname; },
        get port() { return new URL(ORIGINAL_URL).port; },
        get pathname() { return new URL(ORIGINAL_URL).pathname; },
        get search() { return new URL(ORIGINAL_URL).search; },
        get hash() { return window.location.hash; },
        
        assign(url) { window.location.assign(resolveAndEncode(url)); },
        replace(url) { window.location.replace(resolveAndEncode(url)); },
        reload(force) { window.location.reload(force); },
        toString() { return ORIGINAL_URL; }
    };
    
    // Try to override document.location
    try {
        Object.defineProperty(document, 'location', {
            get: () => locationHandler,
            set: (value) => { window.location.href = resolveAndEncode(value); },
            configurable: true
        });
    } catch (e) {}
    
    // Override location on window (where possible)
    try {
        // Create a location-like object that we can use
        window.__uv$location = locationHandler;
    } catch (e) {}
    
    // ==================== HISTORY API OVERRIDE ====================
    
    const originalPushState = History.prototype.pushState;
    const originalReplaceState = History.prototype.replaceState;
    
    History.prototype.pushState = function(state, title, url) {
        if (url) {
            try {
                url = resolveAndEncode(new URL(url, ORIGINAL_URL).href);
            } catch (e) {}
        }
        return originalPushState.call(this, state, title, url);
    };
    
    History.prototype.replaceState = function(state, title, url) {
        if (url) {
            try {
                url = resolveAndEncode(new URL(url, ORIGINAL_URL).href);
            } catch (e) {}
        }
        return originalReplaceState.call(this, state, title, url);
    };
    
    // ==================== ELEMENT ATTRIBUTE OVERRIDE ====================
    
    const urlAttributes = ['href', 'src', 'action', 'data', 'poster', 'srcset', 'formaction'];
    
    const originalSetAttribute = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function(name, value) {
        if (urlAttributes.includes(name.toLowerCase()) && typeof value === 'string' && shouldProxy(value)) {
            if (name.toLowerCase() === 'srcset') {
                value = rewriteSrcset(value);
            } else {
                value = resolveAndEncode(value);
            }
        }
        return originalSetAttribute.call(this, name, value);
    };
    
    const originalGetAttribute = Element.prototype.getAttribute;
    Element.prototype.getAttribute = function(name) {
        const value = originalGetAttribute.call(this, name);
        // Return original value - we could decode here if needed
        return value;
    };
    
    function rewriteSrcset(srcset) {
        return srcset.split(',').map(part => {
            part = part.trim();
            const spaceIdx = part.lastIndexOf(' ');
            if (spaceIdx > 0) {
                const url = part.substring(0, spaceIdx).trim();
                const descriptor = part.substring(spaceIdx).trim();
                return resolveAndEncode(url) + ' ' + descriptor;
            }
            return resolveAndEncode(part);
        }).join(', ');
    }
    
    // ==================== FORM SUBMISSION HANDLER ====================
    
    document.addEventListener('submit', function(e) {
        const form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        
        const action = form.getAttribute('action') || ORIGINAL_URL;
        const method = (form.method || 'GET').toUpperCase();
        
        if (method === 'GET') {
            e.preventDefault();
            
            // Build URL with form data
            const formData = new FormData(form);
            const params = new URLSearchParams();
            
            for (const [key, value] of formData.entries()) {
                if (typeof value === 'string') {
                    params.append(key, value);
                }
            }
            
            let targetUrl;
            try {
                targetUrl = new URL(action, ORIGINAL_URL);
            } catch (err) {
                targetUrl = new URL(ORIGINAL_URL);
                targetUrl.pathname = action;
            }
            
            // Merge existing and new params
            for (const [key, value] of params.entries()) {
                targetUrl.searchParams.set(key, value);
            }
            
            window.location.href = encodeUrl(targetUrl.href);
        } else {
            // For POST, just update the action
            if (action && !action.startsWith(PROXY_PREFIX)) {
                originalSetAttribute.call(form, 'action', resolveAndEncode(action));
            }
        }
    }, true);
    
    // ==================== LINK CLICK HANDLER ====================
    
    document.addEventListener('click', function(e) {
        let target = e.target;
        
        // Find closest anchor
        while (target && target.tagName !== 'A') {
            target = target.parentElement;
        }
        
        if (!target || !target.href) return;
        
        const href = target.getAttribute('href');
        if (!href || !shouldProxy(href)) return;
        
        // Check if already proxied
        if (href.startsWith(PROXY_PREFIX)) return;
        
        e.preventDefault();
        window.location.href = resolveAndEncode(href);
    }, true);
    
    // ==================== MUTATION OBSERVER ====================
    
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    rewriteElement(node);
                }
            }
        }
    });
    
    function rewriteElement(element) {
        // Rewrite URL attributes
        for (const attr of urlAttributes) {
            if (element.hasAttribute && element.hasAttribute(attr)) {
                const value = originalGetAttribute.call(element, attr);
                if (value && shouldProxy(value) && !value.startsWith(PROXY_PREFIX)) {
                    if (attr === 'srcset') {
                        originalSetAttribute.call(element, attr, rewriteSrcset(value));
                    } else {
                        originalSetAttribute.call(element, attr, resolveAndEncode(value));
                    }
                }
            }
        }
        
        // Handle children
        if (element.querySelectorAll) {
            const children = element.querySelectorAll('*');
            for (const child of children) {
                rewriteElement(child);
            }
        }
    }
    
    // Start observing
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            if (document.body) {
                observer.observe(document.body, { childList: true, subtree: true });
            }
        });
    }
    
    // ==================== STYLE SHEET HANDLING ====================
    
    // Intercept style element creation
    const originalAppendChild = Node.prototype.appendChild;
    Node.prototype.appendChild = function(child) {
        if (child && child.tagName === 'STYLE' && child.textContent) {
            // Rewrite CSS URLs
            child.textContent = rewriteCssUrls(child.textContent);
        }
        return originalAppendChild.call(this, child);
    };
    
    function rewriteCssUrls(css) {
        return css.replace(/url\((['"]?)([^'"()]+)\1\)/gi, (match, quote, url) => {
            if (!shouldProxy(url)) return match;
            const proxied = resolveAndEncode(url.trim());
            return `url(${quote}${proxied}${quote})`;
        });
    }
    
    // ==================== COOKIE HANDLING ====================
    
    // Override document.cookie to handle cookies properly
    const cookieDescriptor = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') ||
                             Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie');
    
    if (cookieDescriptor) {
        Object.defineProperty(document, 'cookie', {
            get() {
                return cookieDescriptor.get.call(document);
            },
            set(value) {
                // Modify cookie domain/path if needed
                cookieDescriptor.set.call(document, value);
            },
            configurable: true
        });
    }
    
    // ==================== POSTMESSAGE OVERRIDE ====================
    
    const originalPostMessage = window.postMessage;
    window.postMessage = function(message, targetOrigin, transfer) {
        // Translate origin
        if (targetOrigin === ORIGINAL_ORIGIN) {
            targetOrigin = window.location.origin;
        } else if (targetOrigin === '*') {
            // Keep as-is
        }
        return originalPostMessage.call(window, message, targetOrigin, transfer);
    };
    
    // ==================== DOCUMENT.DOMAIN OVERRIDE ====================
    
    try {
        Object.defineProperty(document, 'domain', {
            get() { return new URL(ORIGINAL_URL).hostname; },
            set(value) { /* ignore */ },
            configurable: true
        });
    } catch (e) {}
    
    // ==================== NAVIGATOR OVERRIDES ====================
    
    try {
        // Make sendBeacon use proxied URLs
        const originalSendBeacon = navigator.sendBeacon;
        if (originalSendBeacon) {
            navigator.sendBeacon = function(url, data) {
                return originalSendBeacon.call(navigator, resolveAndEncode(url), data);
            };
        }
    } catch (e) {}
    
    // ==================== IMAGE OVERRIDE ====================
    
    const OriginalImage = window.Image;
    window.Image = function(width, height) {
        const img = new OriginalImage(width, height);
        
        // Override src property
        const srcDescriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
        Object.defineProperty(img, 'src', {
            get() { return srcDescriptor.get.call(this); },
            set(value) {
                if (shouldProxy(value)) {
                    value = resolveAndEncode(value);
                }
                srcDescriptor.set.call(this, value);
            }
        });
        
        return img;
    };
    window.Image.prototype = OriginalImage.prototype;
    
    // ==================== REGISTER WITH SERVICE WORKER ====================
    
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({
            type: 'register-url',
            data: { originalUrl: ORIGINAL_URL }
        });
    }
    
    console.log('[UV] Client initialized successfully for:', ORIGINAL_URL);
    
})();
