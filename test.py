from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/test')
def test():
    return {'status': 'ok', 'message': 'Flask is working!'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True) 