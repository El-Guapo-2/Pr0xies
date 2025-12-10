"""
Ultraviolet Python Clone - JavaScript Rewriter
Mirrors the JavaScript js.js and rewrite.script.js functionality

This module handles JavaScript AST transformation for proxying:
- Rewrites property accesses (location, window, document, etc.)
- Handles eval() and Function() calls
- Rewrites import statements
- Wraps global identifiers
"""

import re
import json
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin


class JSRewriter:
    """
    JavaScript rewriter that transforms code to work through the proxy.
    Uses regex-based transformation for reliability and speed.
    """
    
    # Global objects/properties that need to be wrapped
    WRAPPED_GLOBALS = {
        'location', 'window', 'document', 'self', 'top', 'parent', 
        'frames', 'globalThis', 'navigator', 'history'
    }
    
    # Properties that need URL rewriting when accessed
    URL_PROPERTIES = {
        'href', 'src', 'action', 'poster', 'data', 'codebase',
        'origin', 'host', 'hostname', 'pathname', 'protocol',
        'port', 'search', 'hash', 'baseURI', 'URL', 'documentURI',
        'referrer', 'domain'
    }
    
    # Methods that take URLs as arguments
    URL_METHODS = {
        'open', 'fetch', 'assign', 'replace', 'pushState', 'replaceState',
        'postMessage', 'sendBeacon', 'navigate', 'go', 'load'
    }
    
    def __init__(self, ctx):
        """
        Initialize the JS rewriter.
        
        Args:
            ctx: The Ultraviolet context with rewrite methods
        """
        self.ctx = ctx
        self.meta = ctx.meta
        self.master = ctx.master
        self.method_prefix = ctx.data_prefix
    
    def rewrite(self, js: str, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite JavaScript code for proxying.
        
        Args:
            js: The JavaScript code to rewrite
            data: Additional data for context
            
        Returns:
            The rewritten JavaScript code
        """
        return self._recast(js, data or {}, 'rewrite')
    
    def source(self, js: str, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Get the source JavaScript (reverse rewrite).
        
        Args:
            js: The rewritten JavaScript code
            data: Additional data
            
        Returns:
            The source JavaScript code
        """
        return self._recast(js, data or {}, 'source')
    
    def _recast(self, js: str, data: Dict[str, Any], rewrite_type: str) -> str:
        """
        Transform JavaScript code.
        
        Uses a combination of regex-based transformations to handle:
        - Import statements
        - Dynamic imports
        - Property accesses on global objects
        - eval() and Function() calls
        - Global identifier references
        
        Args:
            js: The JavaScript code
            data: Context data
            rewrite_type: 'rewrite' or 'source'
            
        Returns:
            Transformed JavaScript code
        """
        if not js:
            return js
        
        try:
            js = str(js)
            
            if rewrite_type == 'rewrite':
                js = self._rewrite_code(js)
            else:
                js = self._source_code(js)
            
            return js
            
        except Exception as e:
            print(f"JS rewrite error: {e}")
            return js
    
    def _rewrite_code(self, js: str) -> str:
        """Apply all rewrite transformations"""
        
        # Skip our own injected scripts to avoid double-rewriting
        if '__uv-script' in js or 'self.__uv$cookies' in js:
            return js
        
        # Rewrite import statements
        js = self._rewrite_imports(js)
        
        # Rewrite dynamic imports
        js = self._rewrite_dynamic_imports(js)
        
        # Wrap location references
        js = self._wrap_location_references(js)
        
        # Wrap eval calls
        js = self._wrap_eval_calls(js)
        
        # Wrap Function constructor
        js = self._wrap_function_constructor(js)
        
        # Rewrite URL strings in common patterns
        js = self._rewrite_url_patterns(js)
        
        # Wrap property accesses
        js = self._wrap_property_accesses(js)
        
        return js
    
    def _source_code(self, js: str) -> str:
        """Reverse rewrite transformations (basic)"""
        # For source, we mainly need to unwrap our wrapped calls
        # This is used for getting original script content
        
        # Unwrap __uv.$get calls
        js = re.sub(
            r'__uv\.\$get\(([^)]+)\)',
            r'\1',
            js
        )
        
        # Unwrap __uv.rewriteUrl calls
        js = re.sub(
            r'__uv\.rewriteUrl\(([^)]+)\)',
            r'\1',
            js
        )
        
        return js
    
    def _rewrite_imports(self, js: str) -> str:
        """Rewrite static import statements"""
        
        # Pattern for import statements
        # import x from 'path'
        # import { x } from 'path'
        # import * as x from 'path'
        # import 'path'
        import_pattern = re.compile(
            r'''(import\s+(?:(?:[\w*{}\s,]+)\s+from\s+)?)['"]((?:[^'"\\]|\\.)+)['"]''',
            re.MULTILINE
        )
        
        def replace_import(match):
            prefix = match.group(1)
            path = match.group(2)
            
            # Skip if already rewritten or is a data URL
            if path.startswith('data:') or '__uv' in path:
                return match.group(0)
            
            # Rewrite the import path
            rewritten_path = self.ctx.rewrite_url(path)
            return f"{prefix}'{rewritten_path}'"
        
        return import_pattern.sub(replace_import, js)
    
    def _rewrite_dynamic_imports(self, js: str) -> str:
        """Rewrite dynamic import() calls"""
        
        # Pattern for import() calls
        # import('path')
        # import("path")
        import_pattern = re.compile(
            r'''import\s*\(\s*['"]((?:[^'"\\]|\\.)+)['"]\s*\)''',
            re.MULTILINE
        )
        
        def replace_import(match):
            path = match.group(1)
            
            if path.startswith('data:') or '__uv' in path:
                return match.group(0)
            
            rewritten_path = self.ctx.rewrite_url(path)
            return f"import('{rewritten_path}')"
        
        js = import_pattern.sub(replace_import, js)
        
        # Also handle variable-based imports: import(varName)
        # Wrap with rewriteUrl
        var_import_pattern = re.compile(
            r'import\s*\(\s*([^\'"][^)]+)\s*\)',
            re.MULTILINE
        )
        
        def replace_var_import(match):
            var_expr = match.group(1).strip()
            # Skip if already wrapped
            if '__uv' in var_expr:
                return match.group(0)
            return f"import(__uv.rewriteUrl({var_expr}))"
        
        return var_import_pattern.sub(replace_var_import, js)
    
    def _wrap_location_references(self, js: str) -> str:
        """Wrap references to location object"""
        
        # Skip if already contains __uv wrappers (avoid double-wrapping)
        # Replace standalone 'location' with __uv.$get(location)
        # But be careful not to replace in property definitions, etc.
        
        patterns = [
            # window.location -> window.__uv$location (but not if already __uv$)
            (r'\bwindow\.(?!__uv)location\b', f'window.{self.method_prefix}location'),
            # document.location -> document.__uv$location
            (r'\bdocument\.(?!__uv)location\b', f'document.{self.method_prefix}location'),
            # self.location -> self.__uv$location
            (r'\bself\.(?!__uv)location\b', f'self.{self.method_prefix}location'),
            # top.location -> __uv$top.location (prevent frame busting)
            (r'\btop\.(?!__uv)location\b', f'{self.method_prefix}top.location'),
            # parent.location -> __uv$parent.location
            (r'\bparent\.(?!__uv)location\b', f'{self.method_prefix}parent.location'),
            # frames.location -> __uv$frames.location
            (r'\bframes\.(?!__uv)location\b', f'{self.method_prefix}frames.location'),
            # this.location in certain contexts (be conservative)
            (r'\bthis\.(?!__uv)location\b(?=\s*[=;,)\]])', f'this.{self.method_prefix}location'),
        ]
        
        for pattern, replacement in patterns:
            js = re.sub(pattern, replacement, js)
        
        # Handle standalone location assignments and accesses
        # location = x -> __uv.location = x
        # location.href -> __uv.location.href
        
        # This is trickier - we use word boundaries
        # Skip if preceded by __uv or __uv$
        js = re.sub(
            r'(?<![.\w])(?<!__uv\.)(?<!__uv\$)location(?=\s*[.=\[\(])',
            f'{self.master}.location',
            js
        )
        
        return js
    
    def _wrap_eval_calls(self, js: str) -> str:
        """Wrap eval() calls to rewrite code before evaluation"""
        
        # eval(code) -> __uv.eval(eval, code)
        eval_pattern = re.compile(
            r'\beval\s*\(\s*([^)]+)\s*\)',
            re.MULTILINE
        )
        
        def replace_eval(match):
            code_arg = match.group(1).strip()
            # Skip if already wrapped
            if '__uv' in code_arg:
                return match.group(0)
            return f'{self.master}.eval(eval, {code_arg})'
        
        return eval_pattern.sub(replace_eval, js)
    
    def _wrap_function_constructor(self, js: str) -> str:
        """Wrap new Function() calls"""
        
        # new Function(code) -> new Function(__uv.rewriteJS(code))
        func_pattern = re.compile(
            r'new\s+Function\s*\(\s*([^)]+)\s*\)',
            re.MULTILINE
        )
        
        def replace_func(match):
            args = match.group(1).strip()
            # Skip if already wrapped
            if '__uv' in args:
                return match.group(0)
            # The last argument is the function body
            return f'new Function({self.master}.rewriteJS({args}))'
        
        return func_pattern.sub(replace_func, js)
    
    def _rewrite_url_patterns(self, js: str) -> str:
        """Rewrite common URL patterns in JavaScript"""
        
        # Common patterns where URLs appear:
        # fetch('url')
        # xhr.open('GET', 'url')
        # new WebSocket('url')
        # new Worker('url')
        # etc.
        
        # fetch() with string literal
        js = re.sub(
            r'''\bfetch\s*\(\s*['"]((?:[^'"\\]|\\.)+)['"]\s*([,)]?)''',
            lambda m: f"fetch('{self.ctx.rewrite_url(m.group(1))}'{m.group(2)}",
            js
        )
        
        # new Worker() with string literal
        js = re.sub(
            r'''\bnew\s+Worker\s*\(\s*['"]((?:[^'"\\]|\\.)+)['"]''',
            lambda m: f"new Worker('{self.ctx.rewrite_url(m.group(1))}'",
            js
        )
        
        # new WebSocket() with string literal
        js = re.sub(
            r'''\bnew\s+WebSocket\s*\(\s*['"]((?:[^'"\\]|\\.)+)['"]''',
            lambda m: f"new WebSocket('{self.ctx.rewrite_url(m.group(1))}'",
            js
        )
        
        # XMLHttpRequest.open() with string URL
        js = re.sub(
            r'''\.open\s*\(\s*(['"]\w+['"])\s*,\s*['"]((?:[^'"\\]|\\.)+)['"]''',
            lambda m: f".open({m.group(1)}, '{self.ctx.rewrite_url(m.group(2))}'",
            js
        )
        
        return js
    
    def _wrap_property_accesses(self, js: str) -> str:
        """Wrap property accesses on global objects"""
        
        # For complex property access patterns, we wrap with __uv.$get
        # This handles cases like: obj.top, obj.parent, etc.
        
        # .top property (for iframe breaking prevention)
        js = re.sub(
            r'(?<![.\w])(\w+)\.top\b(?!\s*[:\(])',
            lambda m: f'{self.master}.$get({m.group(1)}.top)' 
                      if m.group(1) not in ('Math', 'console', 'JSON', 'Object', 'Array') 
                      else m.group(0),
            js
        )
        
        # .parent property
        js = re.sub(
            r'(?<![.\w])(\w+)\.parent\b(?!\s*[:\(])',
            lambda m: f'{self.master}.$get({m.group(1)}.parent)'
                      if m.group(1) not in ('Math', 'console', 'JSON', 'Object', 'Array', 'Node')
                      else m.group(0),
            js
        )
        
        return js


class ImportMeta:
    """Handle import.meta references"""
    
    @staticmethod
    def rewrite(js: str, ctx) -> str:
        """Rewrite import.meta.url references"""
        # import.meta.url -> __uv.meta.url
        return re.sub(
            r'\bimport\.meta\.url\b',
            f'{ctx.master}.meta.url',
            js
        )


def create_js_wrapper() -> str:
    """
    Create the JavaScript wrapper code that provides the __uv object.
    This is injected into every page to enable client-side rewriting.
    """
    return '''
(function() {
    if (window.__uv) return;
    
    const __uv = {
        location: null,
        meta: {
            url: null,
            base: null,
            origin: location.origin
        },
        methods: {
            setSource: '__uv$setSource',
            source: '__uv$source',
            location: '__uv$location',
            function: '__uv$function',
            string: '__uv$string',
            eval: '__uv$eval',
            parent: '__uv$parent',
            top: '__uv$top'
        },
        rewriteUrl: function(url) {
            if (!url) return url;
            if (url.startsWith('data:') || url.startsWith('blob:') || 
                url.startsWith('javascript:') || url.startsWith('#')) {
                return url;
            }
            try {
                const base = this.meta.base || this.meta.url || location.href;
                const resolved = new URL(url, base);
                return this.meta.origin + '__UV_PREFIX__' + 
                       encodeURIComponent(resolved.href);
            } catch(e) {
                return url;
            }
        },
        sourceUrl: function(url) {
            if (!url) return url;
            const prefix = this.meta.origin + '__UV_PREFIX__';
            if (url.startsWith(prefix)) {
                return decodeURIComponent(url.slice(prefix.length));
            }
            return url;
        },
        rewriteJS: function(code) {
            // Client-side JS rewriting (basic)
            return code;
        },
        rewriteCSS: function(code) {
            // Client-side CSS rewriting (basic)
            return code;
        },
        $get: function(obj) {
            if (obj === window.location) return this.location;
            if (obj === window.parent) return window.__uv$parent || window.parent;
            if (obj === window.top) return window.__uv$top || window.top;
            return obj;
        },
        $wrap: function(name) {
            if (name === 'location') return this.methods.location;
            if (name === 'eval') return this.methods.eval;
            return name;
        },
        eval: function(evalFn, code) {
            return evalFn(this.rewriteJS(String(code)));
        }
    };
    
    window.__uv = __uv;
})();
'''
