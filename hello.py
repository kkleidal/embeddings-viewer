import sys
import json
import flask
from flask import Flask, request, send_from_directory
from convert import *
app = Flask(__name__, static_url_path='')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('data', path)

@app.route("/data.js")
def datajs():
    json_data = json.dumps(convert("data/meta.json", link_prefix="/static/"))
    js = "var chartData = %s;" % json_data
    resp = flask.Response(js)
    resp.headers['Content-Type'] = 'application/javascript'
    return resp

@app.route("/")
def home():
    return send_from_directory('static', 'index.html')


#@app.route('/', defaults={'path': ''})
#@app.route('/<path:path>')
#def catch_all(path):
#        return 'You want path: %s' % path
#
if __name__ == "__main__":
    app.run()
