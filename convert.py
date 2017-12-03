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
    print(color)
    return color

def convert(meta_file_link, link_prefix=None):
    with open(meta_file_link, "r") as f:
        meta = json.load(f)
    assert meta.get("embeddings-viewer-version", "") == 1
    chart = {
        "animationEnabled": True,
        "height": 800,
        "width": 800,
    }
    if "title" in meta:
        chart["title"] = {"text": meta["title"]}
    color_options = dict()
    shape_options = dict()
    extras = OrderedDict()
    fields = set()
    dps = []
    for i, data in enumerate(meta["data"]):
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
        dp = {
            "x": data["x"],
            "y": data["y"],
        }
        tt = "<br/>".join((stringify_extra(extra, link_prefix=link_prefix) for extra in data.get("extras", [])))
        #for extra in data.get("extras", []):
        #    extras[extra["id"]] = {
        #        "type": extra["type"],
        #        "id": extra["id"],
        #        "name": extra["name"]

        #    }
        #    dp[extra["id"]] = extra["value"]
        dp["toolTipContent"] = tt
        dps.append(dp)
    # tt = "<br/>".join((stringify_extra(extra, link_prefix=link_prefix) for extra in extras.values()))
    color_option = sorted(color_options.keys())[0]
    print(color_option)
    vals = sorted(color_options[color_option])
    val_map = {val: i for i, val in enumerate(vals)}
    all_ds = []
    for i, val in enumerate(vals):
        ds = {
            "type": "scatter",
            "markerColor": get_color(val),
            "dataPoints": [dp for i, dp in enumerate(dps) if i in set(color_options[color_option][val])],
        }
        all_ds.append(ds)
    chart["data"] = all_ds
    return chart

if __name__ == "__main__":
    convert("data/meta.json")
    
