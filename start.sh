#!/usr/bin/env bash

echo "Starting Flask API..."

gunicorn \
    --workers 1 \
    --threads 2 \
    --timeout 120 \
    --bind 0.0.0.0:5000 \
    app:app &


sleep 5

echo "Starting Streamlit..."

streamlit run dashboard.py \
    --server.address 0.0.0.0 \
    --server.port $PORT