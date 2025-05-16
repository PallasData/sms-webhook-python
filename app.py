from flask import Flask, request, jsonify
import os
import sqlite3
import re
from datetime import datetime
import requests

app = Flask(__name__)

# Simple test route first
@app.route('/')
def home():
    return "SMS Webhook is Running!"

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': str(datetime.now())})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
