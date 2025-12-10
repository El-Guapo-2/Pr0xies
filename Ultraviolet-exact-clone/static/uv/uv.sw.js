/**
 * Ultraviolet Python Clone - Service Worker
 * Stub service worker for client-side request interception
 * Most actual proxying is handled by the Python server
 */

importScripts('/uv/uv.bundle.js');
importScripts('/uv/uv.config.js');

const config = self.__uv$config;

// Ultraviolet instance
const uv = new Ultraviolet(config);

// Install event
self.addEventListener('install', (event) => {
    console.log('[UV SW] Installing...');
    self.skipWaiting();
});

// Activate event
self.addEventListener('activate', (event) => {
    console.log('[UV SW] Activated');
    event.waitUntil(self.clients.claim());
});

// Fetch event
self.addEventListener('fetch', async (event) => {
    const url = new URL(event.request.url);
    
    // Only intercept requests to our prefix
    if (!url.pathname.startsWith(config.prefix)) {
        return;
    }
    
    // The Python server handles the actual proxying
    // This service worker mainly ensures requests go through correctly
    event.respondWith(handleRequest(event));
});

async function handleRequest(event) {
    const url = new URL(event.request.url);
    const pathname = url.pathname;
    
    // Extract encoded URL from path
    const encodedUrl = pathname.slice(config.prefix.length);
    
    if (!encodedUrl) {
        return new Response('No URL specified', { status: 400 });
    }
    
    try {
        // Decode the URL
        const decodedUrl = config.decodeUrl(encodedUrl);
        
        // Clone request with new URL
        const headers = new Headers(event.request.headers);
        
        // Forward to Python server which handles the actual proxying
        const response = await fetch(event.request.url, {
            method: event.request.method,
            headers: headers,
            body: event.request.method !== 'GET' && event.request.method !== 'HEAD' 
                ? await event.request.arrayBuffer() 
                : undefined,
            redirect: 'manual',
            credentials: 'include'
        });
        
        return response;
    } catch (error) {
        console.error('[UV SW] Error:', error);
        return new Response(`Proxy Error: ${error.message}`, { 
            status: 500,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}

// Message handler
self.addEventListener('message', (event) => {
    if (event.data === 'skipWaiting') {
        self.skipWaiting();
    }
});
