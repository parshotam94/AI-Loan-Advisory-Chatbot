#!/usr/bin/env bash

# 1. Start the Flask Backend via Gunicorn in the background on port 5000
gunicorn --bind 127.0.0.1:5000 app:app &

# 2. Wait a brief moment for the backend to initialize
sleep 3

# 3. Start the Streamlit Frontend directly on the port assigned by Render
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --client.showErrorDetails=false --theme.base=dark