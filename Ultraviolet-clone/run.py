#!/usr/bin/env python3
"""
Ultraviolet Proxy Clone - Launcher Script
Run this script to start the proxy server.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from config import get_config


def main():
    """Start the proxy server."""
    config = get_config()
    
    print("=" * 60)
    print("  🌐 Ultraviolet Proxy Clone - Python Edition")
    print("=" * 60)
    print(f"  Server:    http://{config.HOST}:{config.PORT}")
    print(f"  Prefix:    {config.PROXY_PREFIX}")
    print(f"  Debug:     {config.DEBUG}")
    print("=" * 60)
    print()
    print("  Usage:")
    print(f"    1. Open http://localhost:{config.PORT} in your browser")
    print("    2. Enter a URL or use quick links")
    print("    3. Browse the web through the proxy")
    print()
    print("  Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        app.run(
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)


if __name__ == '__main__':
    main()
