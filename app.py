from flask import Flask, request, jsonify
import os
import sqlite3
import re
from datetime import datetime
import requests
import time

app = Flask(__name__)

# Database path
DB_PATH = "survey_responses.db"

def init_database():
    """Initialize database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create participants table with all fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE,
            consent_status TEXT DEFAULT 'pending',
            consent_timestamp DATETIME,
            email TEXT,
            survey_sent INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_fed_vote_intent TEXT,
            gender TEXT,
            age TEXT,
            education TEXT,
            phone_type TEXT,
            region TEXT,
            notes TEXT
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

def send_sms(to_number, message_body):
    """Send SMS using Twilio API"""
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, phone_number]):
        print("ERROR: Twilio credentials not set")
        return False
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    
    try:
        response = requests.post(
            url,
            auth=(account_sid, auth_token),
            data={
                'To': to_number,
                'From': phone_number,
                'Body': message_body
            }
        )
        
        if response.status_code == 201:
            print(f"SMS sent successfully to {to_number}")
            return True
        else:
            print(f"Failed to send SMS to {to_number}. Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return False

def process_sms_response(from_number, message_body):
    """Process incoming SMS response"""
    print(f"Processing response from {from_number}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Log the response
        cursor.execute(
            "INSERT INTO responses (phone_number, message_body) VALUES (?, ?)",
            (from_number, message_body)
        )
        
        # Process the response
        message_upper = message_body.strip().upper()
        
        if message_upper == "YES":
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                (from_number,)
            )
            
            # Send thank you message
            thank_you_msg = "Thank you for consenting! You'll receive survey links occasionally. Reply STOP anytime to unsubscribe."
            send_sms(from_number, thank_you_msg)
            print(f"Sent consent confirmation to {from_number}")
            
        elif message_upper in ["NO", "STOP"]:
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'declined' WHERE phone_number = ?",
                (from_number,)
            )
            
            # Send opt-out confirmation
            opt_out_msg = "You've been removed from our survey list. Thank you!"
            send_sms(from_number, opt_out_msg)
            print(f"Sent opt-out confirmation to {from_number}")
            
        elif message_upper.startswith("EMAIL") or re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body):
            # Handle both "EMAIL address@email.com" and plain "address@email.com"
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body)
            if email_match:
                email = email_match.group()
                # Update both email AND consent status
                cursor.execute(
                    "UPDATE participants SET email = ?, consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                    (email, from_number)
                )
                
                # Send confirmation for both email and SMS consent
                email_msg = f"Thanks! We've saved your email: {email}. You're now signed up for email surveys. Reply STOP anytime to unsubscribe."
                send_sms(from_number, email_msg)
                print(f"Sent email and consent confirmation to {from_number}")
        else:
            # Handle unknown responses
            help_msg = "Reply YES to consent to SMS surveys, NO to opt out, or provide your email address to sign up for both SMS and email surveys."
            send_sms(from_number, help_msg)
            print(f"Sent help message to {from_number}")
        
        conn.commit()
    except Exception as e:
        print(f"Error processing response: {e}")
    finally:
        conn.close()

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SMS Management Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background-color: #0056b3; }
            #status { margin-top: 10px; padding: 10px; border-radius: 5px; display: none; }
            .success { background-color: #d4edda; color: #155724; }
            .error { background-color: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <h1>SMS Management Dashboard</h1>
        
        <h2>Send Consent Request</h2>
        <div class="form-group">
            <label for="phone">Phone Number:</label>
            <input type="text" id="phone" placeholder="+16478941552">
        </div>
        <button onclick="sendConsent()">Send Consent Request</button>
        
        <h2>View Participants</h2>
        <button onclick="viewParticipants()">View All Participants</button>
        <div id="participants" style="margin-top: 20px;"></div>
        
        <div id="status"></div>
        
        <script>
            function showStatus(message, isSuccess) {
                const status = document.getElementById('status');
                status.textContent = message;
                status.className = isSuccess ? 'success' : 'error';
                status.style.display = 'block';
                setTimeout(() => status.style.display = 'none', 5000);
            }
            
            async function sendConsent() {
                const phone = document.getElementById('phone').value;
                if (!phone) {
                    showStatus('Please enter a phone number', false);
                    return;
                }
                
                try {
                    const response = await fetch('/send_consent', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: `phone_number=${encodeURIComponent(phone)}`
                    });
                    
                    const result = await response.json();
                    showStatus(result.message, response.ok);
                } catch (error) {
                    showStatus('Error: ' + error.message, false);
                }
            }
            
            async function viewParticipants() {
                try {
                    const response = await fetch('/participants');
                    const result = await response.json();
                    
                    const div = document.getElementById('participants');
                    if (result.status === 'success' && result.data.length > 0) {
                        let html = '<table border="1" style="width:100%; border-collapse: collapse;"><tr><th>Phone</th><th>Status</th><th>Email</th></tr>';
                        result.data.forEach(p => {
                            html += `<tr><td>${p.phone_number}</td><td>${p.consent_status}</td><td>${p.email || 'N/A'}</td></tr>`;
                        });
                        html += '</table>';
                        div.innerHTML = html;
                    } else {
                        div.innerHTML = 'No participants found';
                    }
                } catch (error) {
                    showStatus('Error: ' + error.message, false);
                }
            }
        </script>
    </body>
    </html>
    '''

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
        
        print(f"From: {from_number}, Message: {message_body}")
        
        if from_number and message_body:
            process_sms_response(from_number, message_body)
        
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

@app.route('/send_consent', methods=['POST'])
def send_consent_endpoint():
    """Endpoint to send consent request"""
    try:
        phone_number = request.form.get('phone_number')
        if not phone_number:
            return jsonify({'status': 'error', 'message': 'Phone number required'}), 400
        
        # Add to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO participants (phone_number) VALUES (?)",
                (phone_number,)
            )
            conn.commit()
        finally:
            conn.close()
        
        # Send consent request
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
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Get port from environment
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(host='0.0.0.0', port=port)
