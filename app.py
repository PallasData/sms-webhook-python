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
            input[type="text"], input[type="url"], input[type="file"], textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-right: 10px; }
            button:hover { background-color: #0056b3; }
            .secondary-button { background-color: #28a745; }
            .secondary-button:hover { background-color: #218838; }
            #status { margin-top: 10px; padding: 10px; border-radius: 5px; display: none; }
            .success { background-color: #d4edda; color: #155724; }
            .error { background-color: #f8d7da; color: #721c24; }
            .section { border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f8f9fa; }
        </style>
    </head>
    <body>
        <h1>📱 SMS Management Dashboard</h1>
        
        <div class="section">
            <h2>Send Consent Request</h2>
            <div class="form-group">
                <label for="phone">Phone Number:</label>
                <input type="text" id="phone" placeholder="+16478941552">
            </div>
            <button onclick="sendConsent()">Send Consent Request</button>
        </div>
        
        <div class="section">
            <h2>Bulk Upload</h2>
            <div class="form-group">
                <label for="csvFile">Upload CSV file:</label>
                <input type="file" id="csvFile" accept=".csv">
            </div>
            <button class="secondary-button" onclick="uploadCsv()">Send Consent to All Numbers in File</button>
            <div style="margin-top: 10px; font-size: 14px; color: #666;">
                <strong>CSV Format:</strong> First column should be phone numbers. Additional columns: LastFedVoteIntent, Gender, Age, Education, PhoneType, Region, Notes
            </div>
        </div>
        
        <div class="section">
            <h2>Send Survey Link</h2>
            <div class="form-group">
                <label for="surveyUrl">Survey URL:</label>
                <input type="url" id="surveyUrl" placeholder="https://your-survey-link.com">
            </div>
            <div class="form-group">
                <label for="customMessage">Custom Message (optional):</label>
                <textarea id="customMessage" rows="3" placeholder="Enter a custom message..."></textarea>
            </div>
            <button onclick="sendSurvey()">Send Survey to All Consented Participants</button>
        </div>
        
        <div class="section">
            <h2>View Participants</h2>
            <button onclick="viewParticipants()">View All Participants</button>
            <div id="participants" style="margin-top: 20px;"></div>
        </div>
        
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
            
            async function uploadCsv() {
                const fileInput = document.getElementById('csvFile');
                const file = fileInput.files[0];
                
                if (!file) {
                    showStatus('Please select a file first', false);
                    return;
                }
                
                try {
                    const formData = new FormData();
                    formData.append('csv_file', file);
                    
                    const response = await fetch('/upload_csv', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    showStatus(result.message, response.ok);
                } catch (error) {
                    showStatus('Error: ' + error.message, false);
                }
            }
            
            async function sendSurvey() {
                const surveyUrl = document.getElementById('surveyUrl').value;
                const customMessage = document.getElementById('customMessage').value;
                
                if (!surveyUrl) {
                    showStatus('Please enter a survey URL', false);
                    return;
                }
                
                try {
                    let body = `survey_url=${encodeURIComponent(surveyUrl)}`;
                    if (customMessage) {
                        body += `&custom_message=${encodeURIComponent(customMessage)}`;
                    }
                    
                    const response = await fetch('/send_survey', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: body
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
                        let html = '<table><tr><th>Phone</th><th>Status</th><th>Email</th><th>Party</th><th>Gender</th><th>Age</th><th>Region</th></tr>';
                        result.data.forEach(p => {
                            html += `<tr>
                                <td>${p.phone_number}</td>
                                <td>${p.consent_status}</td>
                                <td>${p.email || 'N/A'}</td>
                                <td>${p.last_fed_vote_intent || 'N/A'}</td>
                                <td>${p.gender || 'N/A'}</td>
                                <td>${p.age || 'N/A'}</td>
                                <td>${p.region || 'N/A'}</td>
                            </tr>`;
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

@app.route('/send_survey', methods=['POST'])
def send_survey_endpoint():
    """Endpoint to send survey link"""
    try:
        survey_url = request.form.get('survey_url')
        custom_message = request.form.get('custom_message')
        
        if not survey_url:
            return jsonify({'status': 'error', 'message': 'Survey URL required'}), 400
        
        # Get consented participants who haven't been sent this survey
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT phone_number FROM participants WHERE consent_status = 'consented' AND survey_sent = 0"
        )
        participants = cursor.fetchall()
        conn.close()
        
        if not participants:
            return jsonify({'status': 'success', 'message': 'No consented participants to send survey to'})
        
        message = custom_message or f"Hi! Here's your survey link: {survey_url} Thank you for participating!"
        
        sent_count = 0
        for (phone,) in participants:
            if send_sms(phone, message):
                # Mark as survey sent
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE participants SET survey_sent = 1 WHERE phone_number = ?",
                    (phone,)
                )
                conn.commit()
                conn.close()
                sent_count += 1
            
            time.sleep(1)  # Rate limiting
        
        return jsonify({'status': 'success', 'message': f'Survey sent to {sent_count} participants'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV file upload and send consent requests to all numbers"""
    try:
        if 'csv_file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file uploaded'}), 400
        
        file = request.files['csv_file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No file selected'}), 400
        
        # Read CSV file
        content = file.read().decode('utf-8')
        lines = content.strip().split('\n')
        
        if not lines:
            return jsonify({'status': 'error', 'message': 'Empty file'}), 400
        
        # Parse header row
        headers = [h.strip().lower() for h in lines[0].split(',')]
        
        # Find phone number column
        phone_index = None
        for i, header in enumerate(headers):
            if 'phone' in header:
                phone_index = i
                break
        
        if phone_index is None:
            return jsonify({'status': 'error', 'message': 'No phone number column found'}), 400
        
        consent_message = (
            "Hi! This is Pallas Data. You previously expressed interest in participating in our surveys. "
            "We'd like to text you survey links occasionally. "
            "Reply 'YES' to consent or 'NO' to opt out. "
            "You can also reply with your email address if you want to also get surveys emailed to you. "
            "Thanks!"
        )
        
        sent_count = 0
        processed_count = 0
        
        # Process each row
        for line in lines[1:]:  # Skip header
            if not line.strip():
                continue
                
            values = line.split(',')
            
            # Extract phone number
            if len(values) <= phone_index:
                continue
                
            phone = values[phone_index].strip()
            
            # Clean up phone number - remove non-digits
            phone = re.sub(r'[^\d]', '', phone)
            
            # Add country code (+1) if missing
            if phone and not phone.startswith('1') and len(phone) == 10:
                phone = '1' + phone
            
            if phone and len(phone) >= 10:
                phone = '+' + phone
                
                # Extract demographic data if available
                data = {
                    'phone_number': phone,
                    'last_fed_vote_intent': values[headers.index('lastfedvoteintent')] if 'lastfedvoteintent' in headers and len(values) > headers.index('lastfedvoteintent') else None,
                    'gender': values[headers.index('gender')] if 'gender' in headers and len(values) > headers.index('gender') else None,
                    'age': values[headers.index('age')] if 'age' in headers and len(values) > headers.index('age') else None,
                    'education': values[headers.index('education')] if 'education' in headers and len(values) > headers.index('education') else None,
                    'phone_type': values[headers.index('phonetype')] if 'phonetype' in headers and len(values) > headers.index('phonetype') else None,
                    'region': values[headers.index('region')] if 'region' in headers and len(values) > headers.index('region') else None,
                    'notes': values[headers.index('notes')] if 'notes' in headers and len(values) > headers.index('notes') else None,
                }
                
                # Insert into database with all fields
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO participants 
                        (phone_number, last_fed_vote_intent, gender, age, education, phone_type, region, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data['phone_number'],
                        data['last_fed_vote_intent'],
                        data['gender'],
                        data['age'],
                        data['education'],
                        data['phone_type'],
                        data['region'],
                        data['notes']
                    ))
                    conn.commit()
                    processed_count += 1
                finally:
                    conn.close()
                
                # Send SMS
                if send_sms(phone, consent_message):
                    sent_count += 1
                
                time.sleep(1)  # Rate limiting
        
        return jsonify({
            'status': 'success', 
            'message': f'Processed {processed_count} records. Consent requests sent to {sent_count} numbers.'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Error processing file: ' + str(e)}), 500
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
