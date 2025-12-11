from flask import Flask, request

app = Flask(__name__)

@app.route('/')
def test():
    headers_info = {
        'Host': request.host,
        'X-Forwarded-Host': request.headers.get('X-Forwarded-Host'),
        'X-Forwarded-Proto': request.headers.get('X-Forwarded-Proto'),
        'X-Forwarded-Port': request.headers.get('X-Forwarded-Port'),
        'All Headers': dict(request.headers)
    }
    return str(headers_info)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
