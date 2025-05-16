from flask import Flask, request, jsonify
import os
import sqlite3
import re
from datetime import datetime
import requests

app = Flask(__name__)

# Database path
DB_PATH = "survey_responses.db"

def init_database():
    """Initialize database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create participants table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE,
            consent_status TEXT DEFAULT 'pending',
            consent_timestamp DATETIME,
            email TEXT,
            survey_sent INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create responses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            message_body TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def home():
    return "SMS Webhook is Running!"

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy', 
        'timestamp': str(datetime.now()),
        'database': os.path.exists(DB_PATH)
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Twilio webhook"""
    try:
        from_number = request.form.get('From')
        message_body = request.form.get('Body')
        
        # Log the received message
        print(f"Received SMS from {from_number}: {message_body}")
        
        # Return TwiML response
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {'Content-Type': 'text/xml'}
    except Exception as e:
        print(f"Webhook error: {e}")
        return str(e), 500

@app.route('/participants')
def participants():
    """Get all participants"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM participants")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': [dict(zip(columns, row)) for row in rows]
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Get port from environment
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(host='0.0.0.0', port=port)
