/**
 * Ultraviolet Proxy - Service Worker
 * Intercepts all network requests and routes them through the proxy
 */

const PROXY_PREFIX = '/service/';
const ASSET_PREFIX = '/uv/';

// Store the original URL for each proxied page
const urlMap = new Map();

/**
 * URL-safe Base64 encoding
 */
function encodeUrl(url) {
    try {
        const encoded = btoa(unescape(encodeURIComponent(url)))
            .replace(/\+/g, '-')
            .replace(/\//g, '_')
            .replace(/=/g, '');
        return encoded;
    } catch (e) {
        console.error('[SW] Encode error:', e);
        return null;
    }
}

/**
 * URL-safe Base64 decoding
 */
function decodeUrl(encoded) {
    try {
        // Add padding back
        let padded = encoded.replace(/-/g, '+').replace(/_/g, '/');
        while (padded.length % 4) {
            padded += '=';
        }
        return decodeURIComponent(escape(atob(padded)));
    } catch (e) {
        console.error('[SW] Decode error:', e);
        return null;
    }
}

/**
 * Check if URL should be proxied
 */
function shouldProxy(url) {
    if (!url) return false;
    
    const skipPrefixes = [
        'data:',
        'blob:',
        'javascript:',
        'about:',
        'chrome:',
        'chrome-extension:',
        'moz-extension:',
        'safari-extension:'
    ];
    
    return !skipPrefixes.some(prefix => url.startsWith(prefix));
}

/**
 * Get the original URL from a proxied URL
 */
function getOriginalUrl(proxyUrl) {
    try {
        const url = new URL(proxyUrl);
        const pathname = url.pathname;
        
        if (pathname.startsWith(PROXY_PREFIX)) {
            const encoded = pathname.slice(PROXY_PREFIX.length);
            return decodeUrl(encoded);
        }
        
        return null;
    } catch (e) {
        return null;
    }
}

/**
 * Create a proxied URL from an original URL
 */
function createProxyUrl(originalUrl, baseUrl) {
    if (!originalUrl || !shouldProxy(originalUrl)) {
        return originalUrl;
    }
    
    try {
        // Make absolute URL
        let absolute;
        if (originalUrl.startsWith('//')) {
            const baseUrlObj = new URL(baseUrl);
            absolute = baseUrlObj.protocol + originalUrl;
        } else if (originalUrl.startsWith('/')) {
            const baseUrlObj = new URL(baseUrl);
            absolute = baseUrlObj.origin + originalUrl;
        } else if (!originalUrl.startsWith('http://') && !originalUrl.startsWith('https://')) {
            absolute = new URL(originalUrl, baseUrl).href;
        } else {
            absolute = originalUrl;
        }
        
        const encoded = encodeUrl(absolute);
        return PROXY_PREFIX + encoded;
    } catch (e) {
        console.error('[SW] Error creating proxy URL:', e);
        return originalUrl;
    }
}

/**
 * Rewrite URLs in CSS content
 */
function rewriteCss(css, baseUrl) {
    // Rewrite url() references
    css = css.replace(/url\((['"]?)([^'"()]+)\1\)/gi, (match, quote, url) => {
        if (url.startsWith('data:')) return match;
        const proxied = createProxyUrl(url.trim(), baseUrl);
        return `url(${quote}${proxied}${quote})`;
    });
    
    // Rewrite @import
    css = css.replace(/@import\s+(['"])([^'"]+)\1/gi, (match, quote, url) => {
        const proxied = createProxyUrl(url.trim(), baseUrl);
        return `@import ${quote}${proxied}${quote}`;
    });
    
    return css;
}

/**
 * Handle fetch events
 */
self.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Skip non-http(s) requests
    if (!url.protocol.startsWith('http')) {
        return;
    }
    
    // Skip our own static assets
    if (url.pathname.startsWith('/static/') || 
        url.pathname === '/' || 
        url.pathname === '/search' ||
        url.pathname.startsWith('/uv/')) {
        return;
    }
    
    // Handle proxied requests
    if (url.pathname.startsWith(PROXY_PREFIX)) {
        event.respondWith(handleProxyRequest(event, request, url));
    }
});

/**
 * Handle proxied request
 */
async function handleProxyRequest(event, request, url) {
    const encoded = url.pathname.slice(PROXY_PREFIX.length);
    let targetUrl = decodeUrl(encoded);
    
    if (!targetUrl) {
        return new Response('Invalid encoded URL', { status: 400 });
    }
    
    // Append query string if present
    if (url.search) {
        targetUrl += (targetUrl.includes('?') ? '&' : '?') + url.search.slice(1);
    }
    
    try {
        // Build the fetch request
        const headers = new Headers();
        
        // Copy relevant headers from original request
        const forwardHeaders = [
            'accept',
            'accept-language',
            'content-type',
            'range',
            'if-none-match',
            'if-modified-since'
        ];
        
        for (const header of forwardHeaders) {
            const value = request.headers.get(header);
            if (value) {
                headers.set(header, value);
            }
        }
        
        // Set proper headers for the target
        const targetUrlObj = new URL(targetUrl);
        headers.set('Host', targetUrlObj.host);
        headers.set('Origin', targetUrlObj.origin);
        headers.set('Referer', targetUrl);
        
        // Make the request to our backend proxy
        const proxyRequest = new Request(request.url, {
            method: request.method,
            headers: request.headers,
            body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.blob() : undefined,
            mode: 'same-origin',
            credentials: 'include',
            redirect: 'manual'
        });
        
        const response = await fetch(proxyRequest);
        
        // Handle redirects
        if (response.type === 'opaqueredirect' || 
            [301, 302, 303, 307, 308].includes(response.status)) {
            const location = response.headers.get('Location');
            if (location) {
                const newUrl = new URL(location, targetUrl).href;
                const proxiedLocation = createProxyUrl(newUrl, targetUrl);
                
                return Response.redirect(proxiedLocation, response.status || 302);
            }
        }
        
        const contentType = response.headers.get('Content-Type') || '';
        
        // For HTML and CSS, we need to rewrite URLs
        // But since we're using the backend proxy, it already does this
        // Just pass through the response
        
        // Clone response headers, removing problematic ones
        const newHeaders = new Headers();
        for (const [key, value] of response.headers.entries()) {
            const lowerKey = key.toLowerCase();
            // Skip headers that cause issues
            if (!['content-security-policy', 'x-frame-options', 'content-encoding'].includes(lowerKey)) {
                newHeaders.set(key, value);
            }
        }
        
        return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: newHeaders
        });
        
    } catch (error) {
        console.error('[SW] Fetch error:', error);
        return new Response(`Proxy error: ${error.message}`, { status: 502 });
    }
}

/**
 * Install event
 */
self.addEventListener('install', (event) => {
    console.log('[SW] Installing Ultraviolet Service Worker...');
    self.skipWaiting();
});

/**
 * Activate event
 */
self.addEventListener('activate', (event) => {
    console.log('[SW] Ultraviolet Service Worker activated');
    event.waitUntil(clients.claim());
});

/**
 * Message handler for communication with pages
 */
self.addEventListener('message', (event) => {
    const { type, data } = event.data || {};
    
    if (type === 'register-url') {
        // Store original URL mapping for a client
        urlMap.set(event.source.id, data.originalUrl);
    } else if (type === 'get-original-url') {
        const originalUrl = urlMap.get(event.source.id);
        event.source.postMessage({ type: 'original-url', url: originalUrl });
    }
});

console.log('[SW] Ultraviolet Service Worker loaded');
