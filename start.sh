#!/usr/bin/env bash

gunicorn --workers 1 \
    --threads 2 \
    --timeout 120 \
    --bind 127.0.0.1:5000 app:app &

sleep 3

streamlit run streamlit_app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --client.showErrorDetails=false