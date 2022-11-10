#!/bin/sh

rm -r obj/
mkdir -p obj/
cp src/__main__.py src/core.py obj/
cp -L --recursive src/common obj/

poetry export --without-hashes --output requirements.txt
pip install -r requirements.txt -t obj
rm --recursive obj/boto3* obj/botocore*

mkdir -p dist/
python -m zipapp obj/ -o dist/vcuadmin.pyz