/**
 * Ultraviolet Python Clone - Client Bundle
 * This is the main bundle that provides the Ultraviolet class and utilities
 * for client-side URL rewriting and content transformation.
 */

(function(global) {
    'use strict';
    
    // ==================== CODECS ====================
    
    const codecs = {
        none: {
            encode: (str) => str,
            decode: (str) => str
        },
        
        plain: {
            encode: (str) => str ? encodeURIComponent(str) : str,
            decode: (str) => str ? decodeURIComponent(str) : str
        },
        
        xor: {
            encode(str) {
                if (!str) return str;
                str = String(str);
                let result = '';
                for (let i = 0; i < str.length; i++) {
                    result += i % 2 ? String.fromCharCode(str.charCodeAt(i) ^ 2) : str[i];
                }
                return encodeURIComponent(result);
            },
            decode(str) {
                if (!str) return str;
                str = decodeURIComponent(String(str));
                let result = '';
                for (let i = 0; i < str.length; i++) {
                    result += i % 2 ? String.fromCharCode(str.charCodeAt(i) ^ 2) : str[i];
                }
                return result;
            }
        },
        
        base64: {
            encode(str) {
                if (!str) return str;
                return btoa(encodeURIComponent(String(str)));
            },
            decode(str) {
                if (!str) return str;
                return decodeURIComponent(atob(String(str)));
            }
        }
    };
    
    // ==================== EVENT EMITTER ====================
    
    class EventEmitter {
        constructor() {
            this._events = {};
        }
        
        on(event, listener) {
            if (!this._events[event]) {
                this._events[event] = [];
            }
            this._events[event].push(listener);
            return this;
        }
        
        off(event, listener) {
            if (!this._events[event]) return this;
            const idx = this._events[event].indexOf(listener);
            if (idx > -1) {
                this._events[event].splice(idx, 1);
            }
            return this;
        }
        
        emit(event, ...args) {
            if (!this._events[event]) return false;
            this._events[event].forEach(listener => {
                try {
                    listener.apply(this, args);
                } catch (e) {
                    console.error('Event listener error:', e);
                }
            });
            return true;
        }
        
        once(event, listener) {
            const onceWrapper = (...args) => {
                this.off(event, onceWrapper);
                listener.apply(this, args);
            };
            return this.on(event, onceWrapper);
        }
    }
    
    // ==================== ULTRAVIOLET CLASS ====================
    
    class Ultraviolet extends EventEmitter {
        constructor(options = {}) {
            super();
            
            this.prefix = options.prefix || '/service/';
            this.urlRegex = /^(#|about:|data:|mailto:|blob:|javascript:)/;
            
            // URL encoding/decoding
            const codec = options.codec || 'xor';
            this.encodeUrl = options.encodeUrl || codecs[codec].encode;
            this.decodeUrl = options.decodeUrl || codecs[codec].decode;
            
            // Script paths
            this.bundleScript = options.bundle || '/uv/uv.bundle.js';
            this.handlerScript = options.handler || '/uv/uv.handler.js';
            this.clientScript = options.client || '/uv/uv.client.js';
            this.configScript = options.config || '/uv/uv.config.js';
            
            // Metadata
            this.meta = options.meta || {};
            this.meta.base = this.meta.base || null;
            this.meta.origin = this.meta.origin || location.origin;
            this.meta.url = this.meta.url || '';
            
            // Prefixes
            this.master = '__uv';
            this.dataPrefix = '__uv$';
            this.attributePrefix = '__uv';
            
            // Cookie handling
            this.cookie = {
                serialize: this.serializeCookies.bind(this),
                validateCookie: this.validateCookie.bind(this)
            };
            
            // Attribute checkers
            this.attrs = {
                isUrl: this.isUrlAttr.bind(this),
                isForbidden: (name) => ['http-equiv', 'integrity', 'sandbox', 'nonce', 'crossorigin'].includes(name.toLowerCase()),
                isHtml: (name) => name.toLowerCase() === 'srcdoc',
                isSrcset: (name) => ['srcset', 'imagesrcset'].includes(name.toLowerCase()),
                isStyle: (name) => name.toLowerCase() === 'style'
            };
        }
        
        isUrlAttr(name, tag = '') {
            name = name.toLowerCase();
            if (tag === 'object' && name === 'data') return true;
            return ['src', 'href', 'action', 'poster', 'background', 'ping', 
                    'movie', 'profile', 'data', 'formaction', 'icon', 'manifest',
                    'codebase', 'cite', 'archive', 'longdesc', 'usemap'].includes(name);
        }
        
        rewriteUrl(url, meta) {
            meta = meta || this.meta;
            
            if (!url) return url;
            url = String(url).trim();
            
            if (this.urlRegex.test(url)) return url;
            
            if (url.startsWith('javascript:')) {
                return 'javascript:' + this.rewriteJS(url.slice(11));
            }
            
            try {
                const base = meta.base || meta.url || location.href;
                let resolved;
                
                if (url.startsWith('//')) {
                    resolved = location.protocol + url;
                } else {
                    resolved = new URL(url, base).href;
                }
                
                const origin = meta.origin || location.origin;
                return origin + this.prefix + this.encodeUrl(resolved);
            } catch (e) {
                const origin = meta.origin || location.origin;
                return origin + this.prefix + this.encodeUrl(url);
            }
        }
        
        sourceUrl(url, meta) {
            meta = meta || this.meta;
            
            if (!url) return url;
            if (this.urlRegex.test(url)) return url;
            
            try {
                const origin = meta.origin || location.origin;
                const prefix = origin + this.prefix;
                
                if (url.startsWith(prefix)) {
                    const encoded = url.slice(prefix.length);
                    return this.decodeUrl(encoded);
                }
                
                // Handle relative proxy URLs
                if (url.startsWith(this.prefix)) {
                    const encoded = url.slice(this.prefix.length);
                    return this.decodeUrl(encoded);
                }
                
                return url;
            } catch (e) {
                return url;
            }
        }
        
        rewriteJS(code, data) {
            // Basic JS rewriting - more advanced would use AST
            if (!code) return code;
            return String(code);
        }
        
        rewriteCSS(css, options) {
            if (!css) return css;
            css = String(css);
            
            const urlRegex = /url\(['"]?(.+?)['"]?\)/gm;
            
            return css.replace(urlRegex, (match, url) => {
                if (!url || url.startsWith('data:') || url.startsWith('#')) {
                    return match;
                }
                const rewritten = this.rewriteUrl(url.trim().replace(/['"]/g, ''));
                return `url("${rewritten}")`;
            });
        }
        
        rewriteHtml(html, options) {
            // Basic HTML rewriting - more complex would use DOM parsing
            if (!html) return html;
            return String(html);
        }
        
        validateCookie(cookie, meta, js) {
            if (cookie.httpOnly && js) return false;
            
            const url = meta.url || this.meta.url;
            let hostname, path, protocol;
            
            try {
                const parsed = new URL(url);
                hostname = parsed.hostname;
                path = parsed.pathname;
                protocol = parsed.protocol;
            } catch (e) {
                return false;
            }
            
            const domain = cookie.domain || '';
            if (domain) {
                if (domain.startsWith('.')) {
                    if (!hostname.endsWith(domain.slice(1)) && hostname !== domain.slice(1)) {
                        return false;
                    }
                } else if (hostname !== domain && !hostname.endsWith('.' + domain)) {
                    return false;
                }
            }
            
            if (cookie.secure && protocol === 'http:') return false;
            if (cookie.path && !path.startsWith(cookie.path)) return false;
            
            return true;
        }
        
        serializeCookies(cookies, meta, js) {
            const valid = (cookies || []).filter(c => this.validateCookie(c, meta, js));
            return valid.map(c => `${c.name}=${c.value}`).join('; ');
        }
    }
    
    // Static properties
    Ultraviolet.codec = codecs;
    Ultraviolet.EventEmitter = EventEmitter;
    
    // ==================== EXPORTS ====================
    
    global.Ultraviolet = Ultraviolet;
    
})(typeof self !== 'undefined' ? self : this);
