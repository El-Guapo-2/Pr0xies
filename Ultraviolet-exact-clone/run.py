#!/usr/bin/env python3
"""
Ultraviolet Python Clone - Run Script
Easy way to start the proxy server
"""

import os
import sys

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from config import UVConfig, set_config

def main():
    """Run the Ultraviolet proxy server"""
    
    # Create configuration
    config = UVConfig(
        prefix="/service/",
        codec="xor",
        host="0.0.0.0",
        port=8080,
        debug=False,
        timeout=30,
    )
    
    set_config(config)
    
    # Create app
    app = create_app(config)
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║        Ultraviolet Python Clone - Web Proxy Server        ║
╠═══════════════════════════════════════════════════════════╣
║  URL Prefix: /service/                                    ║
║  Codec: XOR                                               ║
╠═══════════════════════════════════════════════════════════╣
║  Server starting on:                                      ║
║    • http://localhost:8080                                ║
║    • http://0.0.0.0:8080                                  ║
╠═══════════════════════════════════════════════════════════╣
║  Visit http://localhost:8080 to start browsing!           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Run the server
    app.run(
        host=config.host,
        port=config.port,
        debug=config.debug,
        threaded=True
    )


if __name__ == '__main__':
    main()
