import os
import sqlite3
import re
from datetime import datetime
from flask import Flask, request, jsonify
import requests

# Initialize Flask app
app = Flask(__name__)

# Database path
DB_PATH = "survey_responses.db"

# Initialize database
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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

# Send SMS function
def send_sms(to_number, message_body):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, phone_number]):
        return False
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    
    response = requests.post(
        url,
        auth=(account_sid, auth_token),
        data={
            'To': to_number,
            'From': phone_number,
            'Body': message_body
        }
    )
    
    return response.status_code == 201

# Process SMS responses
def process_sms_response(from_number, message_body):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO responses (phone_number, message_body) VALUES (?, ?)",
            (from_number, message_body)
        )
        
        message_upper = message_body.strip().upper()
        
        if message_upper == "YES":
            cursor.execute(
                "UPDATE participants SET consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                (from_number,)
            )
            send_sms(from_number, "Thank you for consenting! You'll receive survey links occasionally. Reply STOP anytime to unsubscribe.")
            
        elif message_upper in ["NO", "STOP"]:
            cursor.execute(
                "UPDATE participants SET consent_status = 'declined' WHERE phone_number = ?",
                (from_number,)
            )
            send_sms(from_number, "You've been removed from our survey list. Thank you!")
            
        elif re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body):
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body)
            email = email_match.group()
            cursor.execute(
                "UPDATE participants SET email = ?, consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                (email, from_number)
            )
            send_sms(from_number, f"Thanks! We've saved your email: {email}. You're now signed up for email surveys. Reply STOP anytime to unsubscribe.")
        else:
            send_sms(from_number, "Reply YES to consent to SMS surveys, NO to opt out, or provide your email address to sign up for both SMS and email surveys.")
        
        conn.commit()
    finally:
        conn.close()

# Routes
@app.route('/')
def home():
    return "SMS Webhook is Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    message_body = request.form.get('Body')
    
    if from_number and message_body:
        process_sms_response(from_number, message_body)
    
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {'Content-Type': 'text/xml'}

@app.route('/send_consent', methods=['POST'])
def send_consent():
    phone_number = request.form.get('phone_number')
    if not phone_number:
        return jsonify({'status': 'error', 'message': 'Phone number required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO participants (phone_number) VALUES (?)", (phone_number,))
    conn.commit()
    conn.close()
    
    consent_message = (
        "Hi! This is Pallas Data. You previously expressed interest in participating in our surveys. "
        "We'd like to text you survey links occasionally. "
        "Reply 'YES' to consent or 'NO' to opt out. "
        "You can also reply with your email address if you want to also get surveys emailed to you. "
        "Thanks!"
    )
    
    if send_sms(phone_number, consent_message):
        return jsonify({'status': 'success', 'message': f'Consent request sent to {phone_number}'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to send SMS'}), 500

@app.route('/participants')
def participants():
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

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': str(datetime.now())})

if __name__ == '__main__':
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
