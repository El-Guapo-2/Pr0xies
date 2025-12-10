/**
 * Ultraviolet Python Clone - Configuration
 * Client-side configuration that matches the server configuration
 */

(function(global) {
    'use strict';
    
    global.__uv$config = {
        prefix: '/service/',
        encodeUrl: Ultraviolet.codec.xor.encode,
        decodeUrl: Ultraviolet.codec.xor.decode,
        handler: '/uv/uv.handler.js',
        client: '/uv/uv.client.js',
        bundle: '/uv/uv.bundle.js',
        config: '/uv/uv.config.js',
        sw: '/uv/uv.sw.js'
    };
    
})(typeof self !== 'undefined' ? self : this);
