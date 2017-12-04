import json
from collections import OrderedDict
import matplotlib.pyplot as plt

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

if __name__ == "__main__":
    convert("data/meta.json")
    
