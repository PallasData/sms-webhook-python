import os
import sqlite3
import re
from datetime import datetime
from flask import Flask, request
import requests

# Initialize Flask app
app = Flask(__name__)

# Database path
DB_PATH = "survey_responses.db"

def init_database():
    """Initialize database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create participants table with additional fields
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
                email_msg = f"Thanks! We've saved your email: {email}. You're now signed up for both SMS and email surveys. Reply STOP anytime to unsubscribe."
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

def send_consent_request(phone_numbers):
    """Send consent request to list of phone numbers"""
    consent_message = (
        "Hi! This is Pallas Data. You previously expressed interest in participating in our surveys. "
        "We'd like to text you survey links occasionally. "
        "Reply 'YES' to consent or 'NO' to opt out. "
        "You can also reply with your email address if you want to also get surveys emailed to you. "
        "Thanks!"
    )
    
    for phone in phone_numbers:
        # Add to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO participants (phone_number) VALUES (?)",
                (phone,)
            )
            conn.commit()
        finally:
            conn.close()
        
        # Send SMS
        send_sms(phone, consent_message)
        # Add small delay for rate limiting
        import time
        time.sleep(1)

def send_survey_link(survey_url, custom_message=None):
    """Send survey link to consented participants"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get consented participants who haven't been sent this survey
    cursor.execute(
        "SELECT phone_number FROM participants WHERE consent_status = 'consented' AND survey_sent = 0"
    )
    participants = cursor.fetchall()
    conn.close()
    
    if not participants:
        print("No consented participants to send survey to.")
        return
    
    message = custom_message or f"Hi! Here's your survey link: {survey_url} Thank you for participating!"
    
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
        
        import time
        time.sleep(1)  # Rate limiting

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Twilio webhook"""
    print(f"=== Webhook called at {datetime.now()} ===")
    print(f"Request form data: {request.form}")
    
    from_number = request.form.get('From')
    message_body = request.form.get('Body')
    
    print(f"From: {from_number}")
    print(f"Message: {message_body}")
    
    # Check if participant exists
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants WHERE phone_number = ?", (from_number,))
    participant = cursor.fetchone()
    print(f"Participant found: {participant}")
    conn.close()
    
    if from_number and message_body:
        process_sms_response(from_number, message_body)
        print("Processing complete!")
    
    # Return TwiML response
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {'Content-Type': 'text/xml'}

@app.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists(DB_PATH)
    }

@app.route('/send_consent', methods=['POST'])
def send_consent_endpoint():
    """Endpoint to send consent request"""
    phone_number = request.form.get('phone_number')
    if phone_number:
        # Ensure participant exists in database before sending
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO participants (phone_number) VALUES (?)",
                (phone_number,)
            )
            conn.commit()
            print(f"Participant {phone_number} added to database")
        finally:
            conn.close()
        
        send_consent_request([phone_number])
        return {'status': 'success', 'message': f'Consent request sent to {phone_number}'}
    return {'status': 'error', 'message': 'Phone number required'}, 400

@app.route('/send_survey', methods=['POST'])
def send_survey_endpoint():
    """Endpoint to send survey link"""
    survey_url = request.form.get('survey_url')
    custom_message = request.form.get('custom_message')
    
    if survey_url:
        send_survey_link(survey_url, custom_message)
        return {'status': 'success', 'message': 'Survey sent to consented participants'}
    return {'status': 'error', 'message': 'Survey URL required'}, 400

@app.route('/participants')
def participants():
    """Get all participants"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants")
    rows = cursor.fetchall()
    conn.close()
    
    return {
        'status': 'success',
        'data': [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
    }

@app.route('/clear_database', methods=['POST'])
def clear_database():
    """Clear all data from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Delete all participants
        cursor.execute("DELETE FROM participants")
        # Delete all responses  
        cursor.execute("DELETE FROM responses")
        # Reset auto-increment counters
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='participants'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='responses'")
        
        conn.commit()
        return {'status': 'success', 'message': 'Database cleared successfully'}
    except Exception as e:  
        return {'status': 'error', 'message': 'Error clearing database: ' + str(e)}, 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/reset_survey_status', methods=['POST'])
def reset_survey_status():
    """Reset survey_sent status for all participants"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE participants SET survey_sent = 0")
        rows_affected = cursor.rowcount
        conn.commit()
        return {'status': 'success', 'message': 'Reset survey status for ' + str(rows_affected) + ' participants'}
    except Exception as e:
        return {'status': 'error', 'message': 'Error resetting survey status: ' + str(e)}, 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV file upload and send consent requests to all numbers"""
    if 'csv_file' not in request.files:
        return {'status': 'error', 'message': 'No file uploaded'}, 400
    
    file = request.files['csv_file']
    if file.filename == '':
        return {'status': 'error', 'message': 'No file selected'}, 400
    
    try:
        # Read CSV file
        content = file.read().decode('utf-8')
        lines = content.strip().split('\n')
        
        if not lines:
            return {'status': 'error', 'message': 'Empty file'}, 400
        
        # Parse header row
        headers = [h.strip().lower() for h in lines[0].split(',')]
        
        # Map column indices
        phone_index = None
        for i, header in enumerate(headers):
            if 'phone' in header:
                phone_index = i
                break
        
        if phone_index is None:
            return {'status': 'error', 'message': 'No phone number column found'}, 400
        
        # Define consent message
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
            
            # Clean up phone number
            phone = re.sub(r'[^\d]', '', phone)  # Remove all non-digits
            
            # Add country code (+1) if missing
            if phone and not phone.startswith('1') and len(phone) == 10:
                phone = '1' + phone
            
            if phone and len(phone) >= 10:
                phone = '+' + phone
                
                # Extract other fields if available
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
                
                # Rate limiting
                import time
                time.sleep(1)
        
        return {
            'status': 'success', 
            'message': f'Processed {processed_count} records. Consent requests sent to {sent_count} numbers.'
        }
        
    except Exception as e:
        print(f"Error in upload_csv: {e}")  # Debug print
        return {'status': 'error', 'message': 'Error processing file: ' + str(e)}, 500 'Reset survey status for ' + str(rows_affected) + ' participants'}
    except Exception as e:
        return {'status': 'error', 'message': 'Error resetting survey status: ' + str(e)}, 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/')
def dashboard():
    """Serve the dashboard HTML"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMS Management Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], input[type="url"], input[type="file"], textarea, select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .secondary-button {
            background-color: #28a745;
        }
        .secondary-button:hover {
            background-color: #218838;
        }
        .danger-button {
            background-color: #dc3545;
        }
        .danger-button:hover {
            background-color: #c82333;
        }
        .section {
            border-bottom: 1px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        .section:last-child {
            border-bottom: none;
        }
        #status {
            padding: 10px;
            margin-top: 10px;
            border-radius: 5px;
            display: none;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .form-row {
            display: flex;
            gap: 10px;
        }
        .form-row input, .form-row button, .form-row select {
            flex: 1;
        }
        .instructions {
            background-color: #e7f3ff;
            border: 1px solid #b8daff;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
            font-size: 14px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        td {
            font-size: 14px;
        }
        .participant-filters {
            background-color: #f8fde7;
            border: 1px solid #d5e7a0;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 SMS Management Dashboard</h1>
        
        <div class="section">
            <h2>Send Consent Request</h2>
            <div class="form-group">
                <label for="phone">Phone Number (e.g., +16478941552):</label>
                <input type="text" id="phone" placeholder="+1234567890">
            </div>
            <button onclick="sendConsent()">Send Consent Request</button>
        </div>
        
        <div class="section">
            <h2>Bulk Upload Consent Requests</h2>
            <div class="form-group">
                <label for="csvFile">Upload CSV file with phone numbers and data:</label>
                <input type="file" id="csvFile" accept=".csv" onchange="showUploadPreview()">
            </div>
            <button class="secondary-button" onclick="uploadCsv()">Send Consent to All Numbers in File</button>
            <div class="instructions">
                <strong>CSV Format:</strong><br>
                • First row should be headers: phone_number, LastFedVoteIntent, Gender, Age, Education, PhoneType, Region, Notes<br>
                • Phone numbers will automatically get +1 prefix if missing<br>
                • All demographic data will be stored for targeting<br>
                • Example row: 2042274796, NDP, Male, 65+, Have university degree, Cell Phone, Prairies, Gender Age
            </div>
            <div id="uploadPreview" style="margin-top: 10px; display: none;">
                <strong>File preview:</strong>
                <pre id="filePreview" style="background-color: #f8f9fa; padding: 10px; border-radius: 3px; max-height: 150px; overflow-y: auto;"></pre>
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
                <textarea id="customMessage" rows="3" placeholder="Enter a custom message to send with the survey link..."></textarea>
            </div>
            
            <div class="participant-filters">
                <strong>Target Specific Groups (optional):</strong>
                <div class="form-row">
                    <select id="filterGender">
                        <option value="">All Genders</option>
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                    </select>
                    <select id="filterAge">
                        <option value="">All Ages</option>
                        <option value="18-34">18-34</option>
                        <option value="35-49">35-49</option>
                        <option value="50-64">50-64</option>
                        <option value="65+">65+</option>
                    </select>
                    <select id="filterRegion">
                        <option value="">All Regions</option>
                        <option value="Prairies">Prairies</option>
                        <option value="Ontario">Ontario</option>
                        <option value="Quebec">Quebec</option>
                        <option value="Atlantic">Atlantic</option>
                        <option value="BC">BC</option>
                    </select>
                </div>
            </div>
            
            <button onclick="sendSurvey()">Send Survey to All Consented Participants</button>
            <button class="secondary-button" onclick="sendSurveyFiltered()">Send Survey to Filtered Group</button>
        </div>
        
        <div class="section">
            <h2>Manage Participants</h2>
            <button onclick="viewParticipants()">View All Participants</button>
            <div id="participantsTable" style="margin-top: 20px; display: none;">
                <table id="participantsData">
                    <thead>
                        <tr>
                            <th>Phone Number</th>
                            <th>Consent Status</th>
                            <th>Email</th>
                            <th>Survey Sent</th>
                            <th>Party</th>
                            <th>Gender</th>
                            <th>Age</th>
                            <th>Education</th>
                            <th>Region</th>
                        </tr>
                    </thead>
                    <tbody id="participantsBody">
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="section">
            <h2>Database Management</h2>
            <p style="color: #6c757d; font-size: 14px;">⚠️ Danger Zone: These actions cannot be undone!</p>
            <button class="danger-button" onclick="clearDatabase()">Clear All Data</button>
            <button onclick="resetSurveySent()">Reset Survey Sent Status</button>
        </div>
        
        <div class="section">
            <h2>App Status</h2>
            <button onclick="checkHealth()">Check App Health</button>
            <div id="healthInfo" style="margin-top: 10px; display: none;">
                <div id="healthStatus"></div>
            </div>
        </div>
        
        <div id="status"></div>
    </div>

    <script>
        const API_BASE = window.location.origin;

        function showStatus(message, isSuccess = true) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = isSuccess ? 'success' : 'error';
            status.style.display = 'block';
            setTimeout(() => {
                status.style.display = 'none';
            }, 5000);
        }

        async function sendConsent() {
            const phone = document.getElementById('phone').value;
            if (!phone) {
                showStatus('Please enter a phone number', false);
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/send_consent`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `phone_number=${encodeURIComponent(phone)}`
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error sending consent request: ' + error.message, false);
            }
        }

        function showUploadPreview() {
            const fileInput = document.getElementById('csvFile');
            const file = fileInput.files[0];
            
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const text = e.target.result;
                    const lines = text.split('\\n').slice(0, 5); // Show first 5 lines
                    document.getElementById('filePreview').textContent = lines.join('\\n') + (text.split('\\n').length > 5 ? '\\n...' : '');
                    document.getElementById('uploadPreview').style.display = 'block';
                };
                reader.readAsText(file);
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
                
                const response = await fetch(`${API_BASE}/upload_csv`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error uploading file: ' + error.message, false);
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
                const body = `survey_url=${encodeURIComponent(surveyUrl)}`;
                const fullBody = customMessage ? 
                    `${body}&custom_message=${encodeURIComponent(customMessage)}` : body;
                
                const response = await fetch(`${API_BASE}/send_survey`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: fullBody
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error sending survey: ' + error.message, false);
            }
        }

        async function sendSurveyFiltered() {
            const surveyUrl = document.getElementById('surveyUrl').value;
            const customMessage = document.getElementById('customMessage').value;
            const gender = document.getElementById('filterGender').value;
            const age = document.getElementById('filterAge').value;
            const region = document.getElementById('filterRegion').value;
            
            if (!surveyUrl) {
                showStatus('Please enter a survey URL', false);
                return;
            }

            try {
                let body = `survey_url=${encodeURIComponent(surveyUrl)}`;
                if (customMessage) body += `&custom_message=${encodeURIComponent(customMessage)}`;
                if (gender) body += `&gender=${encodeURIComponent(gender)}`;
                if (age) body += `&age=${encodeURIComponent(age)}`;
                if (region) body += `&region=${encodeURIComponent(region)}`;
                
                const response = await fetch(`${API_BASE}/send_survey_filtered`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: body
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error sending filtered survey: ' + error.message, false);
            }
        }

        async function viewParticipants() {
            try {
                const response = await fetch(`${API_BASE}/participants`);
                const result = await response.json();
                
                if (result.status === 'success') {
                    const tbody = document.getElementById('participantsBody');
                    tbody.innerHTML = '';
                    
                    if (result.data && result.data.length > 0) {
                        result.data.forEach(participant => {
                            const row = tbody.insertRow();
                            row.insertCell(0).textContent = participant.phone_number;
                            row.insertCell(1).textContent = participant.consent_status;
                            row.insertCell(2).textContent = participant.email || 'N/A';
                            row.insertCell(3).textContent = participant.survey_sent ? 'Yes' : 'No';
                            row.insertCell(4).textContent = participant.last_fed_vote_intent || 'N/A';
                            row.insertCell(5).textContent = participant.gender || 'N/A';
                            row.insertCell(6).textContent = participant.age || 'N/A';
                            row.insertCell(7).textContent = participant.education || 'N/A';
                            row.insertCell(8).textContent = participant.region || 'N/A';
                        });
                    } else {
                        const row = tbody.insertRow();
                        const cell = row.insertCell(0);
                        cell.colSpan = 9;
                        cell.textContent = 'No participants found';
                        cell.style.textAlign = 'center';
                    }
                    
                    document.getElementById('participantsTable').style.display = 'block';
                    showStatus('Participants loaded successfully', true);
                } else {
                    showStatus('Error loading participants', false);
                }
            } catch (error) {
                showStatus('Error fetching participants: ' + error.message, false);
            }
        }

        async function checkHealth() {
            try {
                const response = await fetch(`${API_BASE}/health`);
                const result = await response.json();
                
                const healthStatus = document.getElementById('healthStatus');
                if (result.status === 'healthy') {
                    healthStatus.innerHTML = `
                        <div style="color: green;">
                            <strong>✅ App is healthy!</strong><br>
                            Timestamp: ${result.timestamp}<br>
                            Database: ${result.database ? 'Connected' : 'Not connected'}
                        </div>
                    `;
                    showStatus('Health check successful', true);
                } else {
                    healthStatus.innerHTML = `<div style="color: red;">❌ App is unhealthy</div>`;
                    showStatus('Health check failed', false);
                }
                
                document.getElementById('healthInfo').style.display = 'block';
            } catch (error) {
                showStatus('Error checking health: ' + error.message, false);
            }
        }

        async function clearDatabase() {
            if (!confirm('Are you sure you want to delete ALL participants and responses? This cannot be undone!')) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/clear_database`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
                
                // Refresh participants view if it's open
                if (document.getElementById('participantsTable').style.display !== 'none') {
                    viewParticipants();
                }
            } catch (error) {
                showStatus('Error clearing database: ' + error.message, false);
            }
        }

        async function resetSurveySent() {
            if (!confirm('Reset survey sent status for all participants?')) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/reset_survey_status`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
                
                // Refresh participants view if it's open
                if (document.getElementById('participantsTable').style.display !== 'none') {
                    viewParticipants();
                }
            } catch (error) {
                showStatus('Error resetting survey status: ' + error.message, false);
            }
        }
    </script>
</body>
</html>'''
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .secondary-button {
            background-color: #28a745;
        }
        .secondary-button:hover {
            background-color: #218838;
        }
        .danger-button {
            background-color: #dc3545;
        }
        .danger-button:hover {
            background-color: #c82333;
        }
        .section {
            border-bottom: 1px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        .section:last-child {
            border-bottom: none;
        }
        #status {
            padding: 10px;
            margin-top: 10px;
            border-radius: 5px;
            display: none;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .form-row {
            display: flex;
            gap: 10px;
        }
        .form-row input, .form-row button {
            flex: 1;
        }
        .instructions {
            background-color: #e7f3ff;
            border: 1px solid #b8daff;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 SMS Management Dashboard</h1>
        
        <div class="section">
            <h2>Send Consent Request</h2>
            <div class="form-group">
                <label for="phone">Phone Number (e.g., +16478941552):</label>
                <input type="text" id="phone" placeholder="+1234567890">
            </div>
            <button onclick="sendConsent()">Send Consent Request</button>
        </div>
        
        <div class="section">
            <h2>Bulk Upload Consent Requests</h2>
            <div class="form-group">
                <label for="csvFile">Upload CSV file with phone numbers:</label>
                <input type="file" id="csvFile" accept=".csv" onchange="showUploadPreview()">
            </div>
            <button class="secondary-button" onclick="uploadCsv()">Send Consent to All Numbers in File</button>
            <div class="instructions">
                <strong>CSV Format:</strong><br>
                • First column should contain phone numbers<br>
                • Include country code (e.g., +1 for US/Canada)<br>
                • Header row is optional<br>
                • Example: +16478941552, +15551234567
            </div>
            <div id="uploadPreview" style="margin-top: 10px; display: none;">
                <strong>File preview:</strong>
                <pre id="filePreview" style="background-color: #f8f9fa; padding: 10px; border-radius: 3px; max-height: 150px; overflow-y: auto;"></pre>
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
                <textarea id="customMessage" rows="3" placeholder="Enter a custom message to send with the survey link..."></textarea>
            </div>
            <button onclick="sendSurvey()">Send Survey to All Consented Participants</button>
        </div>
        
        <div class="section">
            <h2>Manage Participants</h2>
            <button onclick="viewParticipants()">View All Participants</button>
            <div id="participantsTable" style="margin-top: 20px; display: none;">
                <table id="participantsData" style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f8f9fa;">
                            <th style="border: 1px solid #ddd; padding: 8px;">Phone Number</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Consent Status</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Email</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Survey Sent</th>
                        </tr>
                    </thead>
                    <tbody id="participantsBody">
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="section">
            <h2>Database Management</h2>
            <p style="color: #6c757d; font-size: 14px;">⚠️ Danger Zone: These actions cannot be undone!</p>
            <button class="danger-button" onclick="clearDatabase()">Clear All Data</button>
            <button onclick="resetSurveySent()">Reset Survey Sent Status</button>
        </div>
        
        <div class="section">
            <h2>App Status</h2>
            <button onclick="checkHealth()">Check App Health</button>
            <div id="healthInfo" style="margin-top: 10px; display: none;">
                <div id="healthStatus"></div>
            </div>
        </div>
        
        <div id="status"></div>
    </div>

    <script>
        const API_BASE = window.location.origin;

        function showStatus(message, isSuccess = true) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = isSuccess ? 'success' : 'error';
            status.style.display = 'block';
            setTimeout(() => {
                status.style.display = 'none';
            }, 5000);
        }

        async function sendConsent() {
            const phone = document.getElementById('phone').value;
            if (!phone) {
                showStatus('Please enter a phone number', false);
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/send_consent`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `phone_number=${encodeURIComponent(phone)}`
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error sending consent request: ' + error.message, false);
            }
        }

        function showUploadPreview() {
            const fileInput = document.getElementById('csvFile');
            const file = fileInput.files[0];
            
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const text = e.target.result;
                    const lines = text.split('\\n').slice(0, 5); // Show first 5 lines
                    document.getElementById('filePreview').textContent = lines.join('\\n') + (text.split('\\n').length > 5 ? '\\n...' : '');
                    document.getElementById('uploadPreview').style.display = 'block';
                };
                reader.readAsText(file);
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
                
                const response = await fetch(`${API_BASE}/upload_csv`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error uploading file: ' + error.message, false);
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
                const body = `survey_url=${encodeURIComponent(surveyUrl)}`;
                const fullBody = customMessage ? 
                    `${body}&custom_message=${encodeURIComponent(customMessage)}` : body;
                
                const response = await fetch(`${API_BASE}/send_survey`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: fullBody
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error sending survey: ' + error.message, false);
            }
        }

        async function viewParticipants() {
            try {
                const response = await fetch(`${API_BASE}/participants`);
                const result = await response.json();
                
                if (result.status === 'success') {
                    const tbody = document.getElementById('participantsBody');
                    tbody.innerHTML = '';
                    
                    if (result.data && result.data.length > 0) {
                        result.data.forEach(participant => {
                            const row = tbody.insertRow();
                            row.insertCell(0).textContent = participant.phone_number;
                            row.insertCell(1).textContent = participant.consent_status;
                            row.insertCell(2).textContent = participant.email || 'N/A';
                            row.insertCell(3).textContent = participant.survey_sent ? 'Yes' : 'No';
                        });
                    } else {
                        const row = tbody.insertRow();
                        const cell = row.insertCell(0);
                        cell.colSpan = 4;
                        cell.textContent = 'No participants found';
                        cell.style.textAlign = 'center';
                    }
                    
                    document.getElementById('participantsTable').style.display = 'block';
                    showStatus('Participants loaded successfully', true);
                } else {
                    showStatus('Error loading participants', false);
                }
            } catch (error) {
                showStatus('Error fetching participants: ' + error.message, false);
            }
        }

        async function checkHealth() {
            try {
                const response = await fetch(`${API_BASE}/health`);
                const result = await response.json();
                
                const healthStatus = document.getElementById('healthStatus');
                if (result.status === 'healthy') {
                    healthStatus.innerHTML = `
                        <div style="color: green;">
                            <strong>✅ App is healthy!</strong><br>
                            Timestamp: ${result.timestamp}<br>
                            Database: ${result.database ? 'Connected' : 'Not connected'}
                        </div>
                    `;
                    showStatus('Health check successful', true);
                } else {
                    healthStatus.innerHTML = `<div style="color: red;">❌ App is unhealthy</div>`;
                    showStatus('Health check failed', false);
                }
                
                document.getElementById('healthInfo').style.display = 'block';
            } catch (error) {
                showStatus('Error checking health: ' + error.message, false);
            }
        }

        async function clearDatabase() {
            if (!confirm('Are you sure you want to delete ALL participants and responses? This cannot be undone!')) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/clear_database`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
                
                // Refresh participants view if it's open
                if (document.getElementById('participantsTable').style.display !== 'none') {
                    viewParticipants();
                }
            } catch (error) {
                showStatus('Error clearing database: ' + error.message, false);
            }
        }

        async function resetSurveySent() {
            if (!confirm('Reset survey sent status for all participants?')) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/reset_survey_status`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
                
                // Refresh participants view if it's open
                if (document.getElementById('participantsTable').style.display !== 'none') {
                    viewParticipants();
                }
            } catch (error) {
                showStatus('Error resetting survey status: ' + error.message, false);
            }
        }
    </script>
</body>
</html>'''

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Get port from environment (for cloud deployment)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)

@app.route('/send_survey_filtered', methods=['POST'])
def send_survey_filtered():
    """Send survey link to filtered participants"""
    survey_url = request.form.get('survey_url')
    custom_message = request.form.get('custom_message')
    gender = request.form.get('gender')
    age = request.form.get('age')
    region = request.form.get('region')
    
    if not survey_url:
        return {'status': 'error', 'message': 'Survey URL required'}, 400
    
    # Build query with filters
    query = "SELECT phone_number FROM participants WHERE consent_status = 'consented' AND survey_sent = 0"
    params = []
    
    if gender:
        query += " AND gender = ?"
        params.append(gender)
    if age:
        query += " AND age = ?"
        params.append(age)
    if region:
        query += " AND region = ?"
        params.append(region)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    participants = cursor.fetchall()
    conn.close()
    
    if not participants:
        return {'status': 'success', 'message': 'No participants found matching the criteria'}
    
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
        
        import time
        time.sleep(1)  # Rate limiting
    
    filter_description = []
    if gender: filter_description.append(f"Gender: {gender}")
    if age: filter_description.append(f"Age: {age}")
    if region: filter_description.append(f"Region: {region}")
    
    filter_text = f" ({', '.join(filter_description)})" if filter_description else " (all consented participants)"
    
    return {
        'status': 'success', 
        'message': f'Survey sent to {sent_count} participants{filter_text}'
    }
