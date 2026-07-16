#!/usr/bin/env bash

# 1. Start the Flask Backend via Gunicorn in the background on port 5000
gunicorn --workers 1 --threads 2 --timeout 120 --bind 127.0.0.1:5000 app:app &

# 2. Wait a brief moment for the backend to initialize
sleep 3

# 3. Start the Streamlit Frontend on the specific port required by Hugging Face (7860)
streamlit run streamlit_app.py --server.port 7860 --server.address 0.0.0.0 --client.showErrorDetails=false