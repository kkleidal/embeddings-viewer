#!/usr/bin/env python

import sys
import os
import scipy
import scipy.misc
import json
import flask
from flask import Flask, request, send_from_directory
import json
from collections import OrderedDict
import matplotlib.pyplot as plt
import tempfile
import shutil
import tarfile
import uuid
import io
import numpy as np

DIR = os.path.dirname(os.path.abspath(__file__))

##############
### FLASK ###
##############

class EmbeddingsFlaskApp:
    def __init__(self, embeddings_file):
        self.embeddings_file = embeddings_file
        self.tempdir = None
        self.entered = False

    def __enter__(self):
        self.tempdir = tempfile.mkdtemp()
        name = self.embeddings_file
        fileobj = None
        if not isinstance(name, str):
            fileobj = name
            name = None
        print("Extracting to: %s" % self.tempdir)
        with tarfile.open(name=name, fileobj=fileobj, mode="r:gz") as tar:
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tar, self.tempdir)
        self.entered = True

        app = Flask(__name__, static_url_path='')

        @app.route('/static/<path:path>')
        def send_static(path):
            return send_from_directory(self.tempdir, path)

        @app.route("/data.js")
        def datajs():
            json_data = json.dumps(convert(
                os.path.join(self.tempdir, "meta.json"), link_prefix="/static/"))
            js = "var chartData = %s;" % json_data
            resp = flask.Response(js)
            resp.headers['Content-Type'] = 'application/javascript'
            return resp

        @app.route("/")
        def home():
            directory = os.path.join(DIR, 'static')
            return send_from_directory(directory, 'index.html')

        self.app = app
        return self

    def __exit__(self, type, value, tb):
        self.entered = False
        self.app = None
        if self.tempdir is not None:
            shutil.rmtree(self.tempdir)
        self.tempdir = None

    def run(self):
        assert self.entered
        self.app.run()

########################
## EMBEDDINGS WRITER ###
########################

class EmbeddingsExtra:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.uuid = str(uuid.uuid4())

    @property
    def json(self):
        d = self.subjson()
        d["id"] = self.id
        d["name"] = self.name
        return d

    def subjson(self):
        raise NotImplementedError

    def save_resources(self, resources_dir):
        raise NotImplementedError

class TextExtra(EmbeddingsExtra):
    def __init__(self, id, name, text):
        super().__init__(id, name)
        self.text = text
    
    def subjson(self):
        return {
            "type": "text",
            "value": self.text,
        }

    def save_resources(self, resources_dir):
        pass

class ImageExtra(EmbeddingsExtra):
    def __init__(self, id, name, filepath=None, np_array=None,
            img_data=None, extension=None):
        super().__init__(id, name)
        assert filepath is not None or np_array is not None \
                or img_data is not None
        self.filepath = filepath
        self.np_array = np_array
        self.img_data = img_data
        if extension is None:
            if self.filepath is not None:
                extension = os.path.splitext(self.filepath)[1]
            elif self.np_array is not None:
                extension = "png"
            else:
                assert False, "Cannot infer filetype"
        self.extension = extension
        self.filename = "%s.%s" % (self.uuid, self.extension)
        self.loc = os.path.join("resources", self.filename)

    def subjson(self):
        return {
            "type": "image",
            "value": self.loc,
        }

    def save_resources(self, resources_dir):
        loc = os.path.join(resources_dir, self.filename)
        if self.filepath is not None:
            shutil.copyfile(self.filepath, loc)
        elif self.np_array is not None:
            scipy.misc.imsave(loc, self.np_array)
        else:
            with open(loc, "wb") as f:
                f.write(self.img_data)

class EmbeddingsWriter:
    def __init__(self, output_file, title="Untitled", subtitle=""):
        self.output_file = output_file
        self.tempdir = None
        self.entered = False

        self.title = title
        self.subtitle = subtitle

        self.embeddings = []
        self.current_embeddings_name = None
        self.current_embeddings_data = []
        self.current_embeddings_extras = []

    def _adapt_dict(self, d):
        if isinstance(d, list):
            for el in d:
                assert isinstance(el, dict)
                assert "name" in el
                assert "value" in el
            return d
        elif isinstance(d, OrderedDict):
            out = []
            for key, val in d.items():
                out.append({
                    "name": key,
                    "value": val,
                })
            return out
        else:
            assert isinstance(d, dict)
            keys = sorted(d.keys())
            out = []
            for key in keys:
                out.append({
                    "name": key,
                    "value": d[key],
                })
            return out

    def add_embedding(self, x, y, shape_options=[], color_options=[], extras=[]):
        shape_options = self._adapt_dict(shape_options)
        color_options = self._adapt_dict(color_options)
        emb = {
            "x": x,
            "y": y,
            "shapeOptions": shape_options,
            "colorOptions": color_options,
            "extras": [extra.json for extra in extras],
        }
        self.current_embeddings_data.append(emb)
        self.current_embeddings_extras.extend(extras)

    def set_current_embeddings_name(self, name):
        assert self.entered
        self.current_embeddings_name = name

    def clear_current_embeddings(self):
        assert self.entered
        self.current_embeddings_data = []
        self.current_embeddings_extras = []

    def finish_current_embeddings(self, name=None):
        assert self.entered
        if name is not None:
            self.set_current_embeddings_name(name)
        for extra in self.current_embeddings_extras:
            extra.save_resources(self.resources_dir)
        self.embeddings.append({
            "id": self.current_embeddings_name,
            "data": self.current_embeddings_data,
        })
        self.current_embeddings_data = []
        self.current_embeddings_extras = []

    def set_title(self, title):
        self.title = title

    def set_subtitle(self, subtitle):
        self.subtitle = subtitle

    def __enter__(self):
        self.entered = True
        self.tempdir = tempfile.mkdtemp()
        self.resources_dir = os.path.join(self.tempdir, "resources")
        os.makedirs(self.resources_dir, exist_ok=True)
        return self

    def __exit__(self, type, value, tb):
        try:
            if value is None:
                # No error
                if len(self.current_embeddings_data) > 0:
                    self.finish_current_embeddings()
                with open(os.path.join(self.tempdir, "meta.json"), "w") as f:
                    json.dump({
                        "embeddings-viewer-version": 1,
                        "title": self.title,
                        "subtitle": self.subtitle,
                        "data": self.embeddings,
                    }, f)
                name = self.output_file
                fileobj = None
                if not isinstance(name, str):
                    fileobj = name
                    name = None
                with tarfile.open(name=name, fileobj=fileobj, mode="w:gz") as tar:
                    for filename in os.listdir(self.tempdir):
                        tar.add(os.path.join(self.tempdir, filename),
                                arcname=filename)
        finally:
            self.entered = False
            if self.tempdir is not None:
                shutil.rmtree(self.tempdir)

def make_example_embeddings(saveto="test.tar.gz"):
    with EmbeddingsWriter(saveto) as w:
        w.add_embedding(1.2, 3.4,
                shape_options=OrderedDict([("Modality", "image")]),
                color_options=OrderedDict([
                        ("Ground truth label", 9),
                        ("Cluster", 5)
                    ]),
                extras=[
                    TextExtra("modality", "Modality", "image"),
                    TextExtra("gtl", "Ground truth label", "9"),
                    TextExtra("cluster", "Cluster", "5"),
                    ImageExtra("img", "Image",
                        np_array=np.random.randint(0, 256, size=[28, 28, 3])),
                ])
        w.add_embedding(-0.3, 1.5,
                shape_options=OrderedDict([("Modality", "audio")]),
                color_options=OrderedDict([
                        ("Ground truth label", 4),
                        ("Cluster", 6)
                    ]),
                extras=[
                    TextExtra("modality", "Modality", "audio"),
                    TextExtra("gtl", "Ground truth label", "4"),
                    TextExtra("cluster", "Cluster", "6"),
                    ImageExtra("aud", "Audio",
                        np_array=np.random.randint(0, 256, size=[28, 28, 3])),
                ])

############################
### CONVERT TO CANVAS JS ###
############################

def stringify_extra(extra, link_prefix=None):
    if extra["type"] == "image":
        if link_prefix is None:
            link_prefix = ""
        return "<b> %s: </b> <img src=\"%s%s\" alt=\"%s\" width=\"80px\"/>" % (extra["name"], link_prefix, extra["value"], extra["name"])
    else:
        return "<b> %s: </b> %s" % (extra["name"], extra["value"])

def get_color(x, cmap="Paired"):
    cmap = plt.get_cmap("Paired")
    color = "#" + "".join("%02x" % int(255 * x) for x in cmap(x)[:-1])
    return color

def get_shape(x):
    return ["circle", "square", "triangle", "cross"][x % 4]

def convert(meta_file_link, link_prefix=None):
    with open(meta_file_link, "r") as f:
        meta = json.load(f)
    output_charts = {}
    for embeddings_block in meta["data"]:
        embeddings_id = embeddings_block["id"]
        assert meta.get("embeddings-viewer-version", "") == 1
        chart = {
            "animationEnabled": True,
            "axisY": {
                "gridThickness": 0
            },
            "axisX": {},
            "height": 800,
            "width": 800,
        }
        if "title" in meta:
            chart["title"] = {
                    "text": meta["title"],
                    "fontSize": 16
                }
        if "subtitle" in meta:
            chart["subtitles"] = [{
                    "text": meta["subtitle"],
                    "fontSize": 14
                }]
        color_options = OrderedDict()
        shape_options = OrderedDict()
        extras = OrderedDict()
        fields = set()
        dps = []
        for i, data in enumerate(embeddings_block["data"]):
            if "shapeOptions" in data:
                for shape_option in data["shapeOptions"]: 
                    name = shape_option["name"]
                    value = shape_option["value"]
                    if name not in shape_options:
                        shape_options[name] = {}
                    if value not in shape_options[name]:
                        shape_options[name][value] = []
                    shape_options[name][value].append(i)
            if "colorOptions" in data:
                for shape_option in data["colorOptions"]: 
                    name = shape_option["name"]
                    value = shape_option["value"]
                    if name not in color_options:
                        color_options[name] = {}
                    if value not in color_options[name]:
                        color_options[name][value] = []
                    color_options[name][value].append(i)
            x = data["x"]
            y = data["y"]
            dp = {
                "x": x,
                "y": y,
            }
            tt = "<br/>".join((stringify_extra(extra, link_prefix=link_prefix) for extra in data.get("extras", [])))
            dp["toolTipContent"] = tt
            dps.append(dp)
        charts = {}
        chart_template = chart
        for color_option in color_options:
            charts[color_option] = {}
            color_vals = sorted(color_options[color_option])
            color_val_map = {val: i for i, val in enumerate(color_vals)}
            for shape_option in shape_options:
                chart = dict(chart_template)
                shape_vals = sorted(shape_options[shape_option])
                shape_val_map = {val: i for i, val in enumerate(shape_vals)}

                chart["subtitles"] = chart.get("subtitles", []) + [{
                        "text": "Colored by %s; Shapes represent %s" % (color_option, shape_option),
                        "fontSize": 14
                    }]
                all_ds = []
                for i, color_val in enumerate(color_vals):
                    for j, shape_val in enumerate(shape_vals):
                        indices = set(color_options[color_option][color_val]) & set(shape_options[shape_option][shape_val])
                        ds = {
                            "type": "scatter",
                            "markerType": get_shape(shape_val_map[shape_val]),
                            "markerColor": get_color(color_val_map[color_val]),
                            "dataPoints": [dp for z, dp in enumerate(dps) if z in indices],
                        }
                        all_ds.append(ds)
                chart["data"] = all_ds
                charts[color_option][shape_option] = chart
        output_charts[embeddings_id] = charts
    return output_charts
    
##################
### EXECUTABLE ###
##################

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
            description='Embeddings viewer server')
    parser.add_argument('--fake', action='store_true', help='use fake embeddings')
    parser.add_argument('--embeddings', default=None,
            type=argparse.FileType('rb'), help='embeddings file')
    args = parser.parse_args()
    assert (args.fake and args.embeddings is None) \
            or (not args.fake and args.embeddings is not None)
    if args.fake:
        args.embeddings = io.BytesIO()
        make_example_embeddings(args.embeddings)
        args.embeddings.seek(0)
    with EmbeddingsFlaskApp(args.embeddings) as app:
        app.run()
