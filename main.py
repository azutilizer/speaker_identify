#!/usr/bin/env python3

from flask_restful import Api
from flask import Flask, render_template

app = Flask(__name__)
api = Api()
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
api.init_app(app)


@app.route('/')
def RenderMainIndex():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=7000)
