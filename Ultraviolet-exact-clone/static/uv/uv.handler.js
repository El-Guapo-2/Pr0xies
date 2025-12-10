/**
 * Ultraviolet Python Clone - Handler Script
 * Initializes the hooks and applies them to the window
 */

(function(global) {
    'use strict';
    
    if (typeof __uv$config === 'undefined') {
        console.error('[UV] Config not loaded');
        return;
    }
    
    const config = __uv$config;
    
    // Initialize Ultraviolet
    const uv = new Ultraviolet(config);
    
    // Initialize client hooks
    const client = new UVClient(global);
    
    // Store references
    global.__uv = uv;
    global.__uvClient = client;
    
    // Get the current source URL (the original URL we're proxying)
    function getCurrentSource() {
        try {
            const encoded = location.pathname.slice(config.prefix.length);
            if (encoded) {
                return uv.decodeUrl(encoded);
            }
        } catch (e) {}
        return location.href;
    }
    
    // Store original source URL
    uv.source = getCurrentSource();
    global.__uv$source = uv.source;
    
    // Set up location proxy for frame-busting prevention
    global.__uv$top = global;
    global.__uv$parent = global;
    global.__uv$frames = global;
    
    // Rewrite URL helper
    function rewriteUrl(url, base) {
        if (!url) return url;
        
        url = String(url).trim();
        
        try {
            // Handle special URLs that shouldn't be rewritten
            if (url.startsWith('data:') || url.startsWith('blob:') || 
                url.startsWith('javascript:') || url.startsWith('about:') ||
                url.startsWith('mailto:') || url.startsWith('tel:') ||
                url.startsWith('#')) {
                return url;
            }
            
            // Already rewritten?
            if (url.includes(config.prefix)) {
                return url;
            }
            
            // Build absolute URL
            const absoluteUrl = new URL(url, base || uv.source).href;
            
            // Encode and create proxied URL
            return config.prefix + uv.encodeUrl(absoluteUrl);
        } catch (e) {
            console.warn('[UV] URL rewrite error:', e, url);
            return url;
        }
    }
    
    // Source URL helper (decode proxied URL back to original)
    function sourceUrl(url) {
        if (!url) return url;
        
        try {
            const urlObj = new URL(url, location.href);
            
            if (urlObj.pathname.startsWith(config.prefix)) {
                const encoded = urlObj.pathname.slice(config.prefix.length);
                return uv.decodeUrl(encoded);
            }
            
            return url;
        } catch (e) {
            return url;
        }
    }
    
    // Rewrite HTML attributes that contain URLs
    const urlAttrs = ['href', 'src', 'action', 'poster', 'data', 'background', 'cite', 'formaction'];
    const eventAttrs = ['onclick', 'onload', 'onerror', 'onsubmit', 'onmouseover', 'onmouseout', 'onfocus', 'onblur'];
    
    // ====================
    // FORM SUBMISSION HOOK
    // ====================
    document.addEventListener('submit', function(e) {
        const form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        
        // Get the form action
        let action = form.getAttribute('action') || '';
        
        // If action is not already rewritten, rewrite it
        if (action && !action.includes(config.prefix)) {
            const rewritten = rewriteUrl(action, uv.source);
            form.setAttribute('action', rewritten);
        } else if (!action) {
            // No action means submit to current URL
            form.setAttribute('action', location.pathname + location.search);
        }
    }, true);
    
    // ====================
    // LINK CLICK HOOK
    // ====================
    document.addEventListener('click', function(e) {
        let target = e.target;
        
        // Find the closest anchor element
        while (target && target.tagName !== 'A') {
            target = target.parentElement;
        }
        
        if (!target || target.tagName !== 'A') return;
        
        let href = target.getAttribute('href');
        if (!href) return;
        
        // Skip special URLs
        if (href.startsWith('#') || href.startsWith('javascript:') || 
            href.startsWith('data:') || href.startsWith('mailto:') ||
            href.startsWith('tel:') || href.startsWith('blob:')) {
            return;
        }
        
        // If not already rewritten, rewrite and navigate
        if (!href.includes(config.prefix)) {
            e.preventDefault();
            const rewritten = rewriteUrl(href, uv.source);
            if (target.target === '_blank') {
                window.open(rewritten, '_blank');
            } else {
                location.href = rewritten;
            }
        }
    }, true);
    
    // ====================
    // FETCH HOOK
    // ====================
    client.fetch.on('request', (event) => {
        const { input, init = {} } = event.data;
        
        let url = input;
        if (input instanceof Request) {
            url = input.url;
        }
        
        event.data.input = rewriteUrl(url, uv.source);
        
        // Add headers for bare server
        if (!init.headers) init.headers = {};
        event.data.init = init;
    });
    
    client.fetch.override();
    
    // ====================
    // XHR HOOK
    // ====================
    client.xhr.on('open', (event) => {
        const { input } = event.data;
        event.data.input = rewriteUrl(input, uv.source);
    });
    
    client.xhr.on('responseUrl', (event) => {
        const { value } = event.data;
        event.data.value = sourceUrl(value);
    });
    
    client.xhr.overrideOpen();
    client.xhr.overrideResponseUrl();
    
    // ====================
    // ELEMENT HOOK
    // ====================
    client.element.on('setAttribute', (event) => {
        const { name, value } = event.data;
        
        if (urlAttrs.includes(name.toLowerCase()) && value) {
            event.data.value = rewriteUrl(value, uv.source);
        } else if (name.toLowerCase() === 'style' && value) {
            event.data.value = rewriteCssUrls(value);
        } else if (name.toLowerCase() === 'srcset' && value) {
            event.data.value = rewriteSrcset(value);
        }
    });
    
    client.element.on('getAttribute', (event) => {
        // Could restore original URL here if needed
    });
    
    client.element.overrideAttribute();
    
    // Hook common properties
    const elements = [
        global.HTMLAnchorElement,
        global.HTMLAreaElement,
        global.HTMLLinkElement,
        global.HTMLBaseElement,
        global.HTMLFormElement,
        global.HTMLImageElement,
        global.HTMLScriptElement,
        global.HTMLSourceElement,
        global.HTMLIFrameElement,
        global.HTMLEmbedElement,
        global.HTMLObjectElement,
        global.HTMLVideoElement,
        global.HTMLAudioElement,
        global.HTMLTrackElement
    ].filter(Boolean);
    
    // Hook href property
    client.element.hookProperty([
        global.HTMLAnchorElement,
        global.HTMLAreaElement,
        global.HTMLLinkElement,
        global.HTMLBaseElement
    ].filter(Boolean), 'href', {
        get: (target, that) => sourceUrl(target.call(that)),
        set: (target, that, args) => {
            target.call(that, rewriteUrl(args[0], uv.source));
        }
    });
    
    // Hook src property
    client.element.hookProperty([
        global.HTMLImageElement,
        global.HTMLScriptElement,
        global.HTMLSourceElement,
        global.HTMLIFrameElement,
        global.HTMLEmbedElement,
        global.HTMLVideoElement,
        global.HTMLAudioElement,
        global.HTMLTrackElement
    ].filter(Boolean), 'src', {
        get: (target, that) => sourceUrl(target.call(that)),
        set: (target, that, args) => {
            target.call(that, rewriteUrl(args[0], uv.source));
        }
    });
    
    // Hook action property
    if (global.HTMLFormElement) {
        client.element.hookProperty([global.HTMLFormElement], 'action', {
            get: (target, that) => sourceUrl(target.call(that)),
            set: (target, that, args) => {
                target.call(that, rewriteUrl(args[0], uv.source));
            }
        });
    }
    
    // Hook poster property
    if (global.HTMLVideoElement) {
        client.element.hookProperty([global.HTMLVideoElement], 'poster', {
            get: (target, that) => sourceUrl(target.call(that)),
            set: (target, that, args) => {
                target.call(that, rewriteUrl(args[0], uv.source));
            }
        });
    }
    
    // ====================
    // HISTORY HOOK
    // ====================
    client.history.on('pushState', (event) => {
        const { url } = event.data;
        if (url) {
            event.data.url = rewriteUrl(url, uv.source);
        }
    });
    
    client.history.on('replaceState', (event) => {
        const { url } = event.data;
        if (url) {
            event.data.url = rewriteUrl(url, uv.source);
        }
    });
    
    client.history.overridePushState();
    client.history.overrideReplaceState();
    
    // ====================
    // DOCUMENT HOOK
    // ====================
    client.document.on('getCookie', (event) => {
        // Filter cookies for current domain
        const source = uv.source;
        if (source) {
            try {
                const sourceUrl = new URL(source);
                // Could filter cookies by domain here
            } catch (e) {}
        }
    });
    
    client.document.on('setCookie', (event) => {
        // Rewrite domain/path in cookie
        const source = uv.source;
        if (source) {
            try {
                const sourceUrl = new URL(source);
                // Could modify cookie domain/path here
            } catch (e) {}
        }
    });
    
    client.document.overrideCookie();
    
    // Hook document.domain
    try {
        Object.defineProperty(document, 'domain', {
            get: function() {
                try {
                    return new URL(uv.source).hostname;
                } catch (e) {
                    return '';
                }
            },
            set: function(val) {
                // Ignore domain setting
            },
            configurable: true
        });
    } catch (e) {}
    
    // Hook document.referrer
    try {
        Object.defineProperty(document, 'referrer', {
            get: function() {
                return sourceUrl(document.referrer) || '';
            },
            configurable: true
        });
    } catch (e) {}
    
    // ====================
    // MESSAGE HOOK
    // ====================
    client.message.on('postMessage', (event) => {
        const { origin } = event.data;
        
        if (origin && origin !== '*') {
            // Rewrite origin
            event.data.origin = rewriteUrl(origin, uv.source);
        }
    });
    
    client.message.overridePostMessage();
    
    // ====================
    // NAVIGATOR HOOK
    // ====================
    client.navigator.on('sendBeacon', (event) => {
        const { url } = event.data;
        event.data.url = rewriteUrl(url, uv.source);
    });
    
    client.navigator.overrideSendBeacon();
    
    // ====================
    // WORKERS HOOK
    // ====================
    client.workers.on('worker', (event) => {
        const { url } = event.data;
        event.data.url = rewriteUrl(url, uv.source);
    });
    
    client.workers.overrideWorker();
    
    // ====================
    // WEBSOCKET HOOK
    // ====================
    client.websocket.on('construct', (event) => {
        let { url } = event.data;
        
        try {
            const parsedUrl = new URL(url, uv.source);
            
            // Convert to proxy WebSocket URL
            const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const proxyWsUrl = `${wsProtocol}//${location.host}/__uv/ws?url=${encodeURIComponent(parsedUrl.href)}`;
            
            event.data.url = proxyWsUrl;
        } catch (e) {
            console.error('[UV] WebSocket URL error:', e);
        }
    });
    
    client.websocket.overrideWebSocket();
    
    // ====================
    // EVENTSOURCE HOOK
    // ====================
    client.eventSource.on('construct', (event) => {
        const { url } = event.data;
        event.data.url = rewriteUrl(url, uv.source);
    });
    
    client.eventSource.overrideConstruct();
    
    // ====================
    // FUNCTION HOOK
    // ====================
    client.function.on('construct', (event) => {
        const { args } = event.data;
        
        if (args.length > 0) {
            // Rewrite JavaScript in dynamically created functions
            const body = args[args.length - 1];
            if (typeof body === 'string' && body.includes('location')) {
                args[args.length - 1] = rewriteJs(body);
            }
        }
    });
    
    client.function.overrideFunction();
    
    // ====================
    // URL HOOKS
    // ====================
    client.url.overrideObjectURL();
    
    // ====================
    // STYLE HOOK
    // ====================
    client.style.on('setProperty', (event) => {
        const { property, value } = event.data;
        
        // Check if value contains url()
        if (value && typeof value === 'string' && value.includes('url(')) {
            event.data.value = rewriteCssUrls(value);
        }
    });
    
    client.style.overrideSetGetProperty();
    
    // ====================
    // LOCATION EMULATION
    // ====================
    const fakeLocation = client.location.emulate(
        (href) => {
            try {
                return new URL(sourceUrl(href));
            } catch (e) {
                return new URL(href);
            }
        },
        (url) => {
            return rewriteUrl(url, uv.source);
        }
    );
    
    // Set up location proxies - both __uv$location and __uv.location
    try {
        Object.defineProperty(global, '__uv$location', {
            value: fakeLocation,
            writable: false,
            configurable: false
        });
        
        // Also set __uv.location for compatibility with server-side rewriting
        uv.location = fakeLocation;
        global.__uv.location = fakeLocation;
    } catch (e) {
        console.warn('[UV] Failed to set location proxy:', e);
    }
    
    // ====================
    // HELPER FUNCTIONS
    // ====================
    
    function rewriteCssUrls(css) {
        if (!css) return css;
        
        // Rewrite url()
        css = css.replace(/url\s*\(\s*(['"]?)([^'")]+)\1\s*\)/gi, (match, quote, url) => {
            if (url.startsWith('data:')) return match;
            const rewritten = rewriteUrl(url.trim(), uv.source);
            return `url(${quote}${rewritten}${quote})`;
        });
        
        return css;
    }
    
    function rewriteSrcset(srcset) {
        if (!srcset) return srcset;
        
        return srcset.split(',').map(src => {
            const parts = src.trim().split(/\s+/);
            if (parts.length > 0) {
                parts[0] = rewriteUrl(parts[0], uv.source);
            }
            return parts.join(' ');
        }).join(', ');
    }
    
    function rewriteJs(js) {
        if (!js) return js;
        
        // Basic location rewriting
        // This is simplified - the Python server does more comprehensive rewriting
        return js
            .replace(/\blocation\b/g, '__uv$location')
            .replace(/\bdocument\.location\b/g, '__uv$location')
            .replace(/\bwindow\.location\b/g, '__uv$location');
    }
    
    // ====================
    // EXPOSE API
    // ====================
    global.__uv$hook = function(win) {
        // Hook another window (e.g., iframe)
        const iframeClient = new UVClient(win);
        
        // Apply same hooks to iframe
        // This is simplified - full implementation would re-run all hooks
        return iframeClient;
    };
    
    global.__uvRewrite = rewriteUrl;
    global.__uvSource = sourceUrl;
    
    console.log('[UV] Handler initialized');
    
})(typeof self !== 'undefined' ? self : this);
