#!/usr/bin/env bash
set -e
mydate=$(date +%b%d)   # e.g. “Apr29”
zip -r "results_Jasper_${mydate}_coltonmkt.zip" results myresults
echo "Created zip: results_Jasper_${mydate}_coltonmkt.zip"
