"""
Ultraviolet Python Clone - CSS Rewriter
Mirrors the JavaScript css.js functionality
"""

import re
from typing import Optional, Dict, Any


class CSSRewriter:
    """
    CSS rewriter that transforms URLs in CSS content.
    Mirrors the JavaScript CSS class.
    """
    
    # Regex for url() in CSS - from vk6 (https://github.com/ading2210)
    URL_REGEX = re.compile(r"url\(['\"]?(.+?)['\"]?\)", re.MULTILINE)
    
    # Regex for @import rules
    IMPORT_REGEX = re.compile(
        r"@import\s+(url\s*?\(.{0,9999}?\)|['\"].{0,9999}?['\"]|.{0,9999}?)($|\s|;)",
        re.MULTILINE
    )
    
    # Regex for @font-face src
    FONT_SRC_REGEX = re.compile(r"src\s*:\s*([^;]+)", re.MULTILINE)
    
    def __init__(self, ctx):
        """
        Initialize the CSS rewriter.
        
        Args:
            ctx: The Ultraviolet context with rewrite methods
        """
        self.ctx = ctx
        self.meta = ctx.meta
    
    def rewrite(self, css: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite CSS content, transforming all URLs.
        
        Args:
            css: The CSS string to rewrite
            options: Rewrite options (context, etc.)
            
        Returns:
            The rewritten CSS string
        """
        return self._recast(css, options, 'rewrite')
    
    def source(self, css: str, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Get the source CSS (reverse rewrite).
        
        Args:
            css: The rewritten CSS string
            options: Options
            
        Returns:
            The source CSS string
        """
        return self._recast(css, options, 'source')
    
    def _recast(self, css: str, options: Optional[Dict[str, Any]], 
                rewrite_type: str) -> str:
        """
        Transform CSS content based on type (rewrite or source).
        
        Args:
            css: The CSS string
            options: Options
            rewrite_type: 'rewrite' or 'source'
            
        Returns:
            Transformed CSS string
        """
        if not css:
            return css
        
        options = options or {}
        context = options.get('context', 'stylesheet')
        
        try:
            css = str(css)
            
            # Rewrite url() references
            css = self._rewrite_urls(css, rewrite_type)
            
            # Rewrite @import rules
            css = self._rewrite_imports(css, rewrite_type)
            
            return css
            
        except Exception as e:
            print(f"CSS rewrite error: {e}")
            return css
    
    def _rewrite_urls(self, css: str, rewrite_type: str) -> str:
        """Rewrite all url() references in CSS"""
        
        def replace_url(match):
            full_match = match.group(0)
            url = match.group(1)
            
            # Skip data URLs and empty URLs
            if not url or url.startswith('data:') or url.startswith('#'):
                return full_match
            
            # Clean the URL (remove quotes if present)
            url = url.strip().strip('"').strip("'")
            
            if rewrite_type == 'rewrite':
                encoded_url = self.ctx.rewrite_url(url)
            else:
                encoded_url = self.ctx.source_url(url)
            
            return full_match.replace(match.group(1), encoded_url)
        
        return self.URL_REGEX.sub(replace_url, css)
    
    def _rewrite_imports(self, css: str, rewrite_type: str) -> str:
        """Rewrite @import rules in CSS"""
        
        def replace_import(match):
            full_match = match.group(0)
            import_statement = match.group(1)
            
            if not import_statement:
                return full_match
            
            # Handle different @import syntaxes
            # @import url("path");
            # @import "path";
            # @import 'path';
            
            # Pattern for extracting URL from various @import formats
            url_pattern = re.compile(r'^(url\([\'"]?|[\'"]|)(.+?)([\'"]|[\'"]?\)|)$')
            
            def replace_inner(inner_match):
                prefix = inner_match.group(1)
                url = inner_match.group(2)
                suffix = inner_match.group(3)
                
                # Skip if already a url() reference (handled by URL_REGEX)
                if prefix.startswith('url'):
                    return inner_match.group(0)
                
                if rewrite_type == 'rewrite':
                    encoded_url = self.ctx.rewrite_url(url)
                else:
                    encoded_url = self.ctx.source_url(url)
                
                return f"{prefix}{encoded_url}{suffix}"
            
            new_import = url_pattern.sub(replace_inner, import_statement)
            return full_match.replace(import_statement, new_import)
        
        return self.IMPORT_REGEX.sub(replace_import, css)


# CSS properties that may contain URLs
CSS_URL_PROPERTIES = {
    'background', 'background-image', 'border-image', 'border-image-source',
    'content', 'cursor', 'filter', 'list-style', 'list-style-image',
    'mask', 'mask-image', 'offset-path', 'src', 'clip-path'
}

# Dashed equivalents for JavaScript style properties
DASHED_URL_PROPS = [
    'background',
    'background-image',
    'border-image',
    'border-image-source',
    'list-style',
    'list-style-image',
    'cursor',
    'filter',
    'mask',
    'mask-image',
    'clip-path'
]


def is_css_url_property(prop: str) -> bool:
    """Check if a CSS property may contain URLs"""
    prop_lower = prop.lower().replace('_', '-')
    return prop_lower in CSS_URL_PROPERTIES
