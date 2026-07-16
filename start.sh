#!/usr/bin/env bash

echo "Starting Flask"

gunicorn \
--workers 1 \
--threads 2 \
--timeout 120 \
--bind 0.0.0.0:5000 \
app:app &


sleep 10


echo "Starting Streamlit"

streamlit run streamlit_app.py \
--server.address 0.0.0.0 \
--server.port $PORT \
--server.headless true \
--server.enableCORS false \
--server.enableXsrfProtection false