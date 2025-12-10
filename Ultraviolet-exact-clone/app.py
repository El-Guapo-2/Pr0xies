"""
Ultraviolet Python Clone - Main Application
Flask-based web proxy server that mirrors Ultraviolet functionality
"""

import os
import re
import gzip
import brotli
import json
from typing import Optional, Dict, Any, Tuple, List
from urllib.parse import urlparse, urljoin, quote, unquote
from io import BytesIO

from flask import Flask, request, Response, send_from_directory, render_template, make_response
from flask_cors import CORS
import httpx

from config import UVConfig, get_config, set_config
from ultraviolet import Ultraviolet
from cookie_handler import parse_set_cookie, rewrite_set_cookie, get_cookie_store
from rewrite_html import create_html_inject, create_js_inject


# CSP and security headers to remove
CSP_HEADERS = {
    'cross-origin-embedder-policy',
    'cross-origin-opener-policy',
    'cross-origin-resource-policy',
    'content-security-policy',
    'content-security-policy-report-only',
    'expect-ct',
    'feature-policy',
    'origin-isolation',
    'strict-transport-security',
    'upgrade-insecure-requests',
    'x-content-type-options',
    'x-download-options',
    'x-frame-options',
    'x-permitted-cross-domain-policies',
    'x-powered-by',
    'x-xss-protection',
}

# Headers not to forward
BLOCKED_REQUEST_HEADERS = {
    'host', 'connection', 'accept-encoding', 'content-length',
    'transfer-encoding', 'te', 'trailer', 'upgrade', 'proxy-authorization',
    'proxy-connection'
}

# Methods that don't have a body
EMPTY_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def create_app(config: Optional[UVConfig] = None) -> Flask:
    """
    Create and configure the Flask application.
    
    Args:
        config: Optional UVConfig instance
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__, 
                static_folder='static',
                template_folder='templates')
    
    # Enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Set configuration
    if config:
        set_config(config)
    config = get_config()
    
    # Create HTTP client with connection pooling
    http_client = httpx.Client(
        timeout=httpx.Timeout(config.timeout, connect=10.0),
        follow_redirects=False,  # Handle redirects manually
        verify=False,  # Allow self-signed certificates
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    )
    
    # Store in app context
    app.config['UV_CONFIG'] = config
    app.config['HTTP_CLIENT'] = http_client
    
    # ============== Static File Routes ==============
    
    @app.route('/')
    def index():
        """Serve the main page"""
        return render_template('index.html', config=config)
    
    @app.route('/uv/<path:filename>')
    def serve_uv_static(filename):
        """Serve UV static files"""
        return send_from_directory('static/uv', filename)
    
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """Serve static files"""
        return send_from_directory('static', filename)
    
    # ============== Proxy Routes ==============
    
    @app.route(f'{config.prefix}<path:encoded_url>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
    def proxy_request(encoded_url):
        """
        Main proxy handler - processes all proxied requests.
        Mirrors the JavaScript UVServiceWorker.fetch() method.
        """
        try:
            # Create Ultraviolet instance
            uv = Ultraviolet({
                'prefix': config.prefix,
                'codec': config.codec,
                'bundle': config.bundle,
                'handler': config.handler,
                'client': config.client,
                'config': config.config,
            })
            
            # Decode the original URL
            try:
                original_url = uv.decode_url(encoded_url)
            except Exception as e:
                return Response(f"Failed to decode URL: {e}", status=400)
            
            # Forward query string from the proxy request to the original URL
            if request.query_string:
                proxy_qs = request.query_string.decode('utf-8')
                if '?' in original_url:
                    original_url += '&' + proxy_qs
                else:
                    original_url += '?' + proxy_qs
            
            # Parse the original URL
            try:
                parsed = urlparse(original_url)
                if not parsed.scheme:
                    original_url = 'https://' + original_url
                    parsed = urlparse(original_url)
            except Exception as e:
                return Response(f"Invalid URL: {e}", status=400)
            
            # Determine proxy origin - handle Codespaces/reverse proxy environments
            # Check for forwarded headers first (used by Codespaces, nginx, etc.)
            forwarded_proto = request.headers.get('X-Forwarded-Proto', request.scheme)
            forwarded_host = request.headers.get('X-Forwarded-Host', request.host)
            proxy_origin = f"{forwarded_proto}://{forwarded_host}"
            
            # Set up metadata
            uv.meta['url'] = original_url
            uv.meta['base'] = original_url
            uv.meta['origin'] = proxy_origin
            
            # Handle blob URLs
            if parsed.scheme == 'blob':
                return handle_blob_url(original_url)
            
            # Build request headers
            req_headers = build_request_headers(request, parsed)
            
            # Get cookies for this origin
            cookie_store = get_cookie_store()
            origin = f"{parsed.scheme}://{parsed.netloc}"
            cookies = cookie_store.get_cookies(origin)
            if cookies:
                cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
                if req_headers.get('cookie'):
                    req_headers['cookie'] += '; ' + cookie_str
                else:
                    req_headers['cookie'] = cookie_str
            
            # Get request body
            body = None
            if request.method.upper() not in EMPTY_METHODS:
                body = request.get_data()
            
            # Make the request
            try:
                response = http_client.request(
                    method=request.method,
                    url=original_url,
                    headers=req_headers,
                    content=body,
                    follow_redirects=False
                )
            except httpx.ConnectError as e:
                return Response(f"Connection failed: {e}", status=502)
            except httpx.TimeoutException as e:
                return Response(f"Request timeout: {e}", status=504)
            except Exception as e:
                return Response(f"Request failed: {e}", status=502)
            
            # Process response
            return process_response(response, uv, config, request)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(f"Proxy error: {e}", status=500)
    
    def build_request_headers(flask_request, parsed_url) -> Dict[str, str]:
        """Build headers for the upstream request"""
        headers = {}
        
        # Default User-Agent to use if not provided
        DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        has_user_agent = False
        
        for key, value in flask_request.headers:
            lower_key = key.lower()
            if lower_key not in BLOCKED_REQUEST_HEADERS:
                headers[key] = value
                if lower_key == 'user-agent':
                    has_user_agent = True
        
        # Add default User-Agent if not provided
        if not has_user_agent:
            headers['User-Agent'] = DEFAULT_USER_AGENT
        
        # Set proper Host header
        headers['Host'] = parsed_url.netloc
        
        # Set origin/referer if needed
        if 'Origin' in headers or 'origin' in headers:
            headers['Origin'] = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        if 'Referer' in headers or 'referer' in headers:
            # Try to decode the referer
            referer = headers.get('Referer', headers.get('referer', ''))
            if config.prefix in referer:
                try:
                    encoded_ref = referer.split(config.prefix)[1].split('/')[0]
                    uv_temp = Ultraviolet({'prefix': config.prefix, 'codec': config.codec})
                    decoded_ref = uv_temp.decode_url(encoded_ref)
                    headers['Referer'] = decoded_ref
                except Exception:
                    headers['Referer'] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            else:
                headers['Referer'] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        
        # Add/fix Sec-Fetch headers for proper browser fingerprinting
        headers['Sec-Fetch-Dest'] = headers.get('Sec-Fetch-Dest', 'document')
        headers['Sec-Fetch-Mode'] = headers.get('Sec-Fetch-Mode', 'navigate')
        headers['Sec-Fetch-Site'] = 'none'  # Make it look like direct navigation
        headers['Sec-Fetch-User'] = '?1'
        
        # Add modern browser headers
        headers['Sec-Ch-Ua'] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
        headers['Sec-Ch-Ua-Mobile'] = '?0'
        headers['Sec-Ch-Ua-Platform'] = '"Windows"'
        
        # Accept headers
        headers['Accept'] = headers.get('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8')
        headers['Accept-Language'] = headers.get('Accept-Language', 'en-US,en;q=0.9')
        headers['Accept-Encoding'] = 'gzip, deflate, br'
        
        # Upgrade insecure requests
        headers['Upgrade-Insecure-Requests'] = '1'
        
        return headers
    
    def process_response(response: httpx.Response, uv: Ultraviolet, 
                        config: UVConfig, flask_request) -> Response:
        """Process and rewrite the upstream response"""
        
        # Get response headers
        resp_headers = dict(response.headers)
        
        # Process Set-Cookie headers
        if 'set-cookie' in resp_headers:
            set_cookie_values = response.headers.get_list('set-cookie')
            for cookie_header in set_cookie_values:
                cookie = parse_set_cookie(cookie_header)
                if cookie['name']:
                    url = uv.meta.get('url', '')
                    parsed = urlparse(url)
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                    
                    if not cookie.get('domain'):
                        cookie['domain'] = parsed.hostname or ''
                    if not cookie.get('path'):
                        cookie['path'] = '/'
                    
                    cookie_store = get_cookie_store()
                    cookie_store.set_cookie(origin, cookie)
        
        # Remove security headers
        filtered_headers = {}
        for key, value in resp_headers.items():
            if key.lower() not in CSP_HEADERS and key.lower() != 'set-cookie':
                filtered_headers[key] = value
        
        # Handle redirects
        if response.status_code in (301, 302, 303, 307, 308):
            location = resp_headers.get('location', '')
            if location:
                # Rewrite the redirect URL
                rewritten_location = uv.rewrite_url(location)
                filtered_headers['Location'] = rewritten_location
                
                # Return redirect response without body
                flask_response = Response(
                    '',
                    status=response.status_code,
                    headers=filtered_headers
                )
                return flask_response
        
        # Get content type
        content_type = resp_headers.get('content-type', '')
        
        # Get and decompress body
        body = response.content
        
        content_encoding = resp_headers.get('content-encoding', '').lower()
        if content_encoding and body:
            try:
                if content_encoding == 'gzip' and body[:2] == b'\x1f\x8b':
                    body = gzip.decompress(body)
                    filtered_headers.pop('content-encoding', None)
                    filtered_headers.pop('Content-Encoding', None)
                elif content_encoding == 'br':
                    body = brotli.decompress(body)
                    filtered_headers.pop('content-encoding', None)
                    filtered_headers.pop('Content-Encoding', None)
                elif content_encoding == 'deflate':
                    import zlib
                    try:
                        body = zlib.decompress(body)
                    except zlib.error:
                        # Try raw deflate
                        body = zlib.decompress(body, -zlib.MAX_WBITS)
                    filtered_headers.pop('content-encoding', None)
                    filtered_headers.pop('Content-Encoding', None)
            except Exception as e:
                # If decompression fails, just use the raw content
                pass
        
        # Determine content destination (similar to request.destination in JS)
        destination = determine_destination(flask_request, content_type)
        
        # Rewrite body based on content type
        rewritten_body = body
        
        try:
            if destination == 'document' or destination == 'iframe':
                if content_type and 'text/html' in content_type:
                    # Get cookies for injection
                    cookies_str = uv.serialize_cookies(js=True)
                    referrer = flask_request.headers.get('Referer', '')
                    
                    # Create injection
                    inject_head = create_html_inject(
                        uv.handler_script,
                        uv.bundle_script,
                        uv.client_script,
                        uv.config_script,
                        cookies_str,
                        referrer
                    )
                    
                    # Rewrite HTML
                    html_str = body.decode('utf-8', errors='replace')
                    rewritten_html = uv.rewrite_html(html_str, {
                        'document': True,
                        'injectHead': inject_head
                    })
                    rewritten_body = rewritten_html.encode('utf-8')
            
            elif destination == 'script':
                # Rewrite JavaScript
                js_str = body.decode('utf-8', errors='replace')
                rewritten_js = uv.rewrite_js(js_str)
                rewritten_body = rewritten_js.encode('utf-8')
            
            elif destination == 'style':
                # Rewrite CSS
                css_str = body.decode('utf-8', errors='replace')
                rewritten_css = uv.rewrite_css(css_str)
                rewritten_body = rewritten_css.encode('utf-8')
            
            elif destination == 'worker':
                # Rewrite worker script
                js_str = body.decode('utf-8', errors='replace')
                
                # Inject imports at the start
                cookies_str = uv.serialize_cookies(js=True)
                referrer = flask_request.headers.get('Referer', '')
                
                inject_code = create_js_inject(cookies_str, referrer)
                imports = f"""if (!self.__uv) {{
    {inject_code}
    importScripts("{uv.bundle_script}");
    importScripts("{uv.client_script}");
    importScripts("{uv.config_script}");
    importScripts("{uv.handler_script}");
}}
"""
                rewritten_js = imports + uv.rewrite_js(js_str)
                rewritten_body = rewritten_js.encode('utf-8')
                
        except Exception as e:
            print(f"Rewrite error ({destination}): {e}")
            import traceback
            traceback.print_exc()
        
        # Remove headers that shouldn't be passed through
        headers_to_remove = [
            'transfer-encoding', 'content-encoding', 'content-length',
            'connection', 'keep-alive', 'proxy-authenticate', 
            'proxy-authorization', 'te', 'trailers', 'upgrade'
        ]
        for header in list(filtered_headers.keys()):
            if header.lower() in headers_to_remove:
                del filtered_headers[header]
        
        # Set correct content length
        filtered_headers['Content-Length'] = str(len(rewritten_body))
        
        # Add CORS headers
        filtered_headers['Access-Control-Allow-Origin'] = '*'
        filtered_headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        filtered_headers['Access-Control-Allow-Headers'] = '*'
        filtered_headers['Access-Control-Expose-Headers'] = '*'
        
        # Handle cross-origin isolation if needed
        if flask_request.headers.get('Sec-Fetch-Mode') == 'cross-origin':
            filtered_headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
        
        # Create Flask response
        flask_response = Response(
            rewritten_body,
            status=response.status_code,
            headers=filtered_headers
        )
        
        return flask_response
    
    def determine_destination(flask_request, content_type: str) -> str:
        """Determine the request destination (like request.destination in JS)"""
        
        # Check Sec-Fetch-Dest header (modern browsers)
        dest = flask_request.headers.get('Sec-Fetch-Dest', '')
        if dest:
            return dest
        
        # Check Accept header
        accept = flask_request.headers.get('Accept', '')
        
        if 'text/html' in accept:
            return 'document'
        elif 'text/css' in accept:
            return 'style'
        elif 'application/javascript' in accept or 'text/javascript' in accept:
            return 'script'
        elif 'image/' in accept:
            return 'image'
        elif 'font/' in accept or 'application/font' in accept:
            return 'font'
        
        # Check content-type of response
        if content_type:
            if 'text/html' in content_type:
                return 'document'
            elif 'text/css' in content_type:
                return 'style'
            elif 'javascript' in content_type:
                return 'script'
            elif 'image/' in content_type:
                return 'image'
            elif 'font/' in content_type or 'application/font' in content_type:
                return 'font'
        
        return ''
    
    def handle_blob_url(url: str) -> Response:
        """Handle blob: URLs"""
        return Response("Blob URLs must be handled client-side", status=400)
    
    # ============== Error Handlers ==============
    
    @app.errorhandler(404)
    def not_found(e):
        return Response("Not found", status=404)
    
    @app.errorhandler(500)
    def server_error(e):
        return Response(f"Server error: {e}", status=500)
    
    return app


# Create default app instance
app = create_app()


if __name__ == '__main__':
    config = get_config()
    app.run(
        host=config.host,
        port=config.port,
        debug=config.debug,
        threaded=True
    )
