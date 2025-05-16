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
    columns = [description[0] for description in cursor.description]
    conn.close()
    
    return {
        'status': 'success',
        'data': [dict(zip(columns, row)) for row in rows]
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
        return {'status': 'error', 'message': 'Error processing file: ' + str(e)}, 500

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
            
