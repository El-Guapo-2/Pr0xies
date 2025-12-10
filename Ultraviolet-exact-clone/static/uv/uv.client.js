/**
 * Ultraviolet Python Clone - Client Script
 * Provides client-side hooks and overrides for seamless proxying
 */

(function(global) {
    'use strict';
    
    class HookEvent {
        constructor(data, target, that) {
            this.data = data;
            this.target = target;
            this.that = that;
            this.intercepted = false;
            this.returnValue = undefined;
        }
        
        respondWith(value) {
            this.intercepted = true;
            this.returnValue = value;
        }
    }
    
    class EventEmitter {
        constructor() {
            this._events = {};
        }
        
        on(event, listener) {
            if (!this._events[event]) this._events[event] = [];
            this._events[event].push(listener);
            return this;
        }
        
        emit(event, ...args) {
            if (!this._events[event]) return false;
            this._events[event].forEach(fn => fn.apply(this, args));
            return true;
        }
    }
    
    class UVClient extends EventEmitter {
        constructor(window, bareClient, worker = !window.window) {
            super();
            this.window = window;
            this.bareClient = bareClient;
            this.worker = worker;
            
            this.nativeMethods = {
                fnToString: Function.prototype.toString,
                defineProperty: Object.defineProperty,
                getOwnPropertyDescriptor: Object.getOwnPropertyDescriptor,
                getOwnPropertyDescriptors: Object.getOwnPropertyDescriptors,
                getOwnPropertyNames: Object.getOwnPropertyNames,
                keys: Object.keys,
                isArray: Array.isArray,
                setPrototypeOf: Object.setPrototypeOf,
                isExtensible: Object.isExtensible,
                Map: Map,
                Proxy: Proxy
            };
            
            // Initialize subsystems
            this.fetch = new FetchHook(this);
            this.xhr = new XHRHook(this);
            this.element = new ElementHook(this);
            this.node = new NodeHook(this);
            this.document = new DocumentHook(this);
            this.history = new HistoryHook(this);
            this.location = new LocationHook(this);
            this.message = new MessageHook(this);
            this.navigator = new NavigatorHook(this);
            this.url = new URLHook(this);
            this.workers = new WorkersHook(this);
            this.storage = new StorageHook(this);
            this.style = new StyleHook(this);
            this.websocket = new WebSocketHook(this);
            this.function = new FunctionHook(this);
            this.object = new ObjectHook(this);
            this.attribute = new AttributeHook(this);
            this.eventSource = new EventSourceHook(this);
            this.idb = new IDBHook(this);
        }
        
        override(obj, prop, wrapper, construct = false) {
            if (!obj || !obj[prop]) return;
            
            const original = obj[prop];
            const wrapped = function(...args) {
                return wrapper(original, this, args);
            };
            
            if (construct && original.prototype) {
                wrapped.prototype = original.prototype;
                wrapped.prototype.constructor = wrapped;
            }
            
            this.copyProps(original, wrapped);
            obj[prop] = wrapped;
            
            return original;
        }
        
        overrideDescriptor(obj, prop, desc) {
            const original = this.nativeMethods.getOwnPropertyDescriptor(obj, prop);
            if (!original) return;
            
            const newDesc = { ...original };
            
            if (desc.get) {
                newDesc.get = function() {
                    return desc.get(original.get, this);
                };
            }
            
            if (desc.set) {
                newDesc.set = function(val) {
                    return desc.set(original.set, this, val);
                };
            }
            
            this.nativeMethods.defineProperty(obj, prop, newDesc);
            return original;
        }
        
        wrap(obj, prop, wrapper, construct = false) {
            const fn = obj[prop];
            if (!fn) return fn;
            
            const wrapped = function(...args) {
                return wrapper(fn, this, args);
            };
            
            if (construct && fn.prototype) {
                wrapped.prototype = fn.prototype;
                wrapped.prototype.constructor = wrapped;
            }
            
            this.emit('wrap', fn, wrapped, construct);
            return wrapped;
        }
        
        copyProps(from, to) {
            try {
                const nameDesc = this.nativeMethods.getOwnPropertyDescriptor(from, 'name');
                if (nameDesc) this.nativeMethods.defineProperty(to, 'name', nameDesc);
                
                const lengthDesc = this.nativeMethods.getOwnPropertyDescriptor(from, 'length');
                if (lengthDesc) this.nativeMethods.defineProperty(to, 'length', lengthDesc);
            } catch (e) {}
        }
    }
    
    // ==================== SUBSYSTEM HOOKS ====================
    
    class FetchHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.fetch = this.window.fetch;
        }
        
        override() {
            const hook = this;
            
            this.ctx.override(this.window, 'fetch', (target, that, args) => {
                if (!args.length) return target.apply(that, args);
                
                let [input, init] = args;
                
                const event = new HookEvent({ input, init }, target, that);
                hook.emit('request', event);
                
                if (event.intercepted) return event.returnValue;
                
                return target.call(that, event.data.input, event.data.init);
            });
        }
    }
    
    class XHRHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.XMLHttpRequest = this.window.XMLHttpRequest;
            this.xhrProto = this.XMLHttpRequest.prototype;
            this.open = this.xhrProto.open;
            this.send = this.xhrProto.send;
            this.responseURL = ctx.nativeMethods.getOwnPropertyDescriptor(this.xhrProto, 'responseURL');
        }
        
        overrideOpen() {
            const hook = this;
            
            this.ctx.override(this.xhrProto, 'open', (target, that, args) => {
                if (args.length < 2) return target.apply(that, args);
                
                let [method, url, ...rest] = args;
                
                const event = new HookEvent({ method, input: url }, target, that);
                hook.emit('open', event);
                
                if (event.intercepted) return event.returnValue;
                
                return target.call(that, event.data.method, event.data.input, ...rest);
            });
        }
        
        overrideResponseUrl() {
            const hook = this;
            
            this.ctx.overrideDescriptor(this.xhrProto, 'responseURL', {
                get: (target, that) => {
                    const value = target.call(that);
                    const event = new HookEvent({ value }, target, that);
                    hook.emit('responseUrl', event);
                    
                    if (event.intercepted) return event.returnValue;
                    return event.data.value;
                }
            });
        }
    }
    
    class ElementHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.Element = this.window.Element;
            this.elemProto = this.Element ? this.Element.prototype : {};
            this.setAttribute = this.elemProto.setAttribute;
            this.getAttribute = this.elemProto.getAttribute;
            this.removeAttribute = this.elemProto.removeAttribute;
            this.hasAttribute = this.elemProto.hasAttribute;
        }
        
        overrideAttribute() {
            const hook = this;
            
            this.ctx.override(this.elemProto, 'setAttribute', (target, that, args) => {
                if (args.length < 2) return target.apply(that, args);
                
                let [name, value] = args;
                
                const event = new HookEvent({ name, value }, target, that);
                hook.emit('setAttribute', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.name, event.data.value);
            });
            
            this.ctx.override(this.elemProto, 'getAttribute', (target, that, args) => {
                if (!args.length) return target.apply(that, args);
                
                let [name] = args;
                
                const event = new HookEvent({ name }, target, that);
                hook.emit('getAttribute', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.name);
            });
        }
        
        hookProperty(elements, prop, handler) {
            if (!Array.isArray(elements)) elements = [elements];
            
            for (const element of elements) {
                if (!element || !element.prototype) continue;
                
                const desc = this.ctx.nativeMethods.getOwnPropertyDescriptor(element.prototype, prop);
                if (!desc) continue;
                
                const newDesc = { ...desc };
                
                if (handler.get && desc.get) {
                    newDesc.get = function() {
                        return handler.get(desc.get, this);
                    };
                }
                
                if (handler.set && desc.set) {
                    newDesc.set = function(val) {
                        return handler.set(desc.set, this, [val]);
                    };
                }
                
                this.ctx.nativeMethods.defineProperty(element.prototype, prop, newDesc);
            }
        }
    }
    
    class NodeHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.Node = this.window.Node;
            this.nodeProto = this.Node ? this.Node.prototype : {};
            this.baseURI = ctx.nativeMethods.getOwnPropertyDescriptor(this.nodeProto, 'baseURI');
            this.textContent = ctx.nativeMethods.getOwnPropertyDescriptor(this.nodeProto, 'textContent');
        }
    }
    
    class DocumentHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.document = this.window.document;
            this.Document = this.window.Document;
            this.docProto = this.Document ? this.Document.prototype : {};
            this.cookie = ctx.nativeMethods.getOwnPropertyDescriptor(this.docProto, 'cookie');
            this.domain = ctx.nativeMethods.getOwnPropertyDescriptor(this.docProto, 'domain');
            this.referrer = ctx.nativeMethods.getOwnPropertyDescriptor(this.docProto, 'referrer');
        }
        
        overrideCookie() {
            const hook = this;
            
            this.ctx.overrideDescriptor(this.docProto, 'cookie', {
                get: (target, that) => {
                    const value = target.call(that);
                    const event = new HookEvent({ value }, target, that);
                    hook.emit('getCookie', event);
                    
                    if (event.intercepted) return event.returnValue;
                    return event.data.value;
                },
                set: (target, that, [val]) => {
                    const event = new HookEvent({ value: val }, target, that);
                    hook.emit('setCookie', event);
                    
                    if (event.intercepted) return event.returnValue;
                    return target.call(that, event.data.value);
                }
            });
        }
    }
    
    class HistoryHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.History = this.window.History;
            this.historyProto = this.History ? this.History.prototype : {};
            this.pushState = this.historyProto.pushState;
            this.replaceState = this.historyProto.replaceState;
        }
        
        overridePushState() {
            const hook = this;
            
            this.ctx.override(this.historyProto, 'pushState', (target, that, args) => {
                if (args.length < 3) return target.apply(that, args);
                
                let [state, title, url] = args;
                
                const event = new HookEvent({ state, title, url }, target, that);
                hook.emit('pushState', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.state, event.data.title, event.data.url);
            });
        }
        
        overrideReplaceState() {
            const hook = this;
            
            this.ctx.override(this.historyProto, 'replaceState', (target, that, args) => {
                if (args.length < 3) return target.apply(that, args);
                
                let [state, title, url] = args;
                
                const event = new HookEvent({ state, title, url }, target, that);
                hook.emit('replaceState', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.state, event.data.title, event.data.url);
            });
        }
    }
    
    class LocationHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
        }
        
        emulate(parse, wrap) {
            const location = this.window.location;
            const hook = this;
            
            const handler = {
                get(target, prop) {
                    if (prop === 'href') {
                        return parse(location.href).href;
                    }
                    
                    const parsed = parse(location.href);
                    if (prop in parsed) {
                        return parsed[prop];
                    }
                    
                    const val = Reflect.get(target, prop);
                    if (typeof val === 'function') {
                        return val.bind(target);
                    }
                    return val;
                },
                
                set(target, prop, value) {
                    if (prop === 'href') {
                        location.href = wrap(value);
                        return true;
                    }
                    
                    Reflect.set(target, prop, value);
                    return true;
                }
            };
            
            return new Proxy(location, handler);
        }
    }
    
    class MessageHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
        }
        
        overridePostMessage() {
            const hook = this;
            
            this.ctx.override(this.window, 'postMessage', (target, that, args) => {
                if (!args.length) return target.apply(that, args);
                
                let [message, origin, transfer] = args;
                
                const event = new HookEvent({ message, origin, transfer }, target, that);
                hook.emit('postMessage', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.message, event.data.origin, event.data.transfer);
            });
        }
    }
    
    class NavigatorHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.Navigator = this.window.Navigator;
            this.navProto = this.Navigator ? this.Navigator.prototype : {};
        }
        
        overrideSendBeacon() {
            const hook = this;
            
            this.ctx.override(this.navProto, 'sendBeacon', (target, that, args) => {
                if (!args.length) return target.apply(that, args);
                
                let [url, data] = args;
                
                const event = new HookEvent({ url, data }, target, that);
                hook.emit('sendBeacon', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.url, event.data.data);
            });
        }
    }
    
    class URLHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.URL = this.window.URL;
            this.createObjectURL = this.URL.createObjectURL;
            this.revokeObjectURL = this.URL.revokeObjectURL;
        }
        
        overrideObjectURL() {
            const hook = this;
            
            this.ctx.override(this.URL, 'createObjectURL', (target, that, args) => {
                if (!args.length) return target.apply(that, args);
                
                let [object] = args;
                
                const event = new HookEvent({ object }, target, that);
                hook.emit('createObjectURL', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.object);
            });
            
            this.ctx.override(this.URL, 'revokeObjectURL', (target, that, args) => {
                if (!args.length) return target.apply(that, args);
                
                let [url] = args;
                
                const event = new HookEvent({ url }, target, that);
                hook.emit('revokeObjectURL', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.url);
            });
        }
    }
    
    class WorkersHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.Worker = this.window.Worker;
        }
        
        overrideWorker() {
            const hook = this;
            
            this.ctx.override(this.window, 'Worker', (target, that, args) => {
                if (!args.length) return new target(...args);
                
                let [url, options] = args;
                
                const event = new HookEvent({ url, options }, target, that);
                hook.emit('worker', event);
                
                if (event.intercepted) return event.returnValue;
                return new target(event.data.url, event.data.options);
            }, true);
        }
    }
    
    class StorageHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.localStorage = this.window.localStorage;
            this.sessionStorage = this.window.sessionStorage;
            this.Storage = this.window.Storage;
            this.storeProto = this.Storage ? this.Storage.prototype : {};
        }
    }
    
    class StyleHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.CSSStyleDeclaration = this.window.CSSStyleDeclaration;
            this.cssProto = this.CSSStyleDeclaration ? this.CSSStyleDeclaration.prototype : {};
        }
        
        overrideSetGetProperty() {
            const hook = this;
            const cssText = this.ctx.nativeMethods.getOwnPropertyDescriptor(this.cssProto, 'cssText');
            
            this.ctx.override(this.cssProto, 'setProperty', (target, that, args) => {
                if (args.length < 2) return target.apply(that, args);
                
                let [property, value, priority] = args;
                
                const event = new HookEvent({ property, value, priority }, target, that);
                hook.emit('setProperty', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.property, event.data.value, event.data.priority);
            });
            
            this.ctx.override(this.cssProto, 'getPropertyValue', (target, that, args) => {
                if (!args.length) return target.apply(that, args);
                
                let [property] = args;
                
                const event = new HookEvent({ property }, target, that);
                hook.emit('getPropertyValue', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that, event.data.property);
            });
        }
    }
    
    class WebSocketHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.WebSocket = this.window.WebSocket;
        }
        
        overrideWebSocket(bareClient) {
            const hook = this;
            
            this.ctx.override(this.window, 'WebSocket', (target, that, args) => {
                if (!args.length) return new target(...args);
                
                let [url, protocols] = args;
                
                const event = new HookEvent({ url, protocols }, target, that);
                hook.emit('construct', event);
                
                if (event.intercepted) return event.returnValue;
                return new target(event.data.url, event.data.protocols);
            }, true);
        }
    }
    
    class FunctionHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.Function = this.window.Function;
        }
        
        overrideFunction() {
            const hook = this;
            const original = this.Function;
            
            const wrapped = function(...args) {
                const event = new HookEvent({ args }, original, this);
                hook.emit('construct', event);
                
                if (event.intercepted) return event.returnValue;
                return new original(...event.data.args);
            };
            
            wrapped.prototype = original.prototype;
            this.window.Function = wrapped;
        }
        
        overrideToString() {
            const hook = this;
            
            this.ctx.override(Function.prototype, 'toString', (target, that, args) => {
                const event = new HookEvent({}, target, that);
                hook.emit('toString', event);
                
                if (event.intercepted) return event.returnValue;
                return target.call(that);
            });
        }
    }
    
    class ObjectHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
        }
    }
    
    class AttributeHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.Attr = this.window.Attr;
            this.attrProto = this.Attr ? this.Attr.prototype : {};
        }
    }
    
    class EventSourceHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.EventSource = this.window.EventSource;
        }
        
        overrideConstruct() {
            const hook = this;
            
            this.ctx.override(this.window, 'EventSource', (target, that, args) => {
                if (!args.length) return new target(...args);
                
                let [url, options] = args;
                
                const event = new HookEvent({ url, options }, target, that);
                hook.emit('construct', event);
                
                if (event.intercepted) return event.returnValue;
                return new target(event.data.url, event.data.options);
            }, true);
        }
    }
    
    class IDBHook extends EventEmitter {
        constructor(ctx) {
            super();
            this.ctx = ctx;
            this.window = ctx.window;
            this.indexedDB = this.window.indexedDB;
        }
    }
    
    // Export
    global.UVClient = UVClient;
    global.HookEvent = HookEvent;
    
})(typeof self !== 'undefined' ? self : this);
