#!/bin/bash
cd /Users/user/Documents/GitHub/kubelingo
python3 -m kubelingo.k8s_manifest_generator --mode question --question-count 1 --topic mcq --backends ollama