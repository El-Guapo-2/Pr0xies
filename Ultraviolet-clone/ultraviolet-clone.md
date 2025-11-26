# Ultraviolet Proxy Clone - Python Edition

A Python implementation of the Ultraviolet web proxy, allowing users to browse the web through a proxy layer.

## Features

- 🌐 **Web Proxy**: Browse any website through the proxy
- 🔒 **URL Encoding**: Base64 URL encoding for obfuscation
- 📝 **HTML Rewriting**: Automatic URL rewriting in HTML content
- 🎨 **CSS Rewriting**: URL rewriting in stylesheets
- 📜 **JavaScript Interception**: Client-side hooks for dynamic content
- ⚡ **Fast**: Built with Flask for efficient request handling
- 🎯 **Modern UI**: Clean, responsive interface

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Start the Server

```bash
python run.py
```

Or directly:
```bash
python app.py
```

The server will start at `http://localhost:8080`

### Configuration

Environment variables:
- `UV_HOST`: Server host (default: `0.0.0.0`)
- `UV_PORT`: Server port (default: `8080`)
- `UV_DEBUG`: Enable debug mode (default: `true`)
- `UV_PREFIX`: Proxy URL prefix (default: `/service/`)
- `UV_ENV`: Environment (`development` or `production`)

### API Endpoints

- `GET /` - Main page with search interface
- `GET /search?url=<URL>` - Redirect to proxied URL
- `GET /service/<encoded_url>` - Proxy endpoint

## Project Structure

```
Ultraviolet-clone/
├── app.py              # Main Flask application
├── run.py              # Launcher script
├── config.py           # Configuration settings
├── utils.py            # Utility functions
├── rewriter.py         # Content rewriting module
├── requirements.txt    # Python dependencies
├── templates/
│   ├── index.html      # Main page template
│   └── error.html      # Error page template
└── static/
    ├── style.css       # Stylesheet
    └── script.js       # Client-side JavaScript
```

## How It Works

1. **URL Encoding**: When you visit a URL through the proxy, it gets encoded using URL-safe Base64
2. **Request Proxying**: The server fetches the target page on your behalf
3. **Content Rewriting**: All URLs in HTML/CSS are rewritten to go through the proxy
4. **Script Injection**: Client-side JavaScript intercepts dynamic requests (fetch, XHR, etc.)

## Limitations

- Some complex JavaScript applications may not work perfectly
- WebSocket connections are not supported in this version
- Some sites may block proxy requests based on headers

## License

MIT License - Feel free to use and modify!
