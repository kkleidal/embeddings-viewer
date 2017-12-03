#!/bin/bash

source activate embeddings-viewer
FLASK_APP=hello.py flask run -h 0.0.0.0
