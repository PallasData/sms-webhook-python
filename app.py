import os
import sqlite3
import re
import csv
import io
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, Response
import requests

# Initialize Flask app
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            calltime TEXT,
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
        print(f"Processing message: '{message_upper}'")
        
        # Check if the participant exists in the database with EXACT match
        cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (from_number,))
        participant = cursor.fetchone()
        
        if not participant:
            print(f"Searching for alternative formats for number {from_number}")
            # Try searching for the number without the '+' prefix
            if from_number.startswith('+'):
                alt_number = from_number[1:]  # Remove the '+' prefix
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
            
            # Try searching with '+' prefix
            if not participant and not from_number.startswith('+') and from_number.isdigit():
                alt_number = '+' + from_number
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
                
            # If we still can't find it, try removing the country code if it's there
            if not participant and (from_number.startswith('+1') or from_number.startswith('1')):
                if from_number.startswith('+1'):
                    alt_number = from_number[2:]  # Remove the '+1' prefix
                elif from_number.startswith('1'):
                    alt_number = from_number[1:]  # Remove the '1' prefix
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
                
            if not participant:
                print(f"No participant found for number {from_number} after trying alternative formats")
                # Send a message that we couldn't identify them
                help_msg = "We couldn't identify your number in our system. Please text START to join our survey list."
                send_sms(from_number, help_msg)
                return
        
        # Get the actual phone number as stored in database
        stored_number = participant[0]
        print(f"Found participant with number: {stored_number}")
        
        if message_upper == "YES":
            print(f"Processing YES response for {stored_number}")
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                (stored_number,)
            )
            rows_affected = cursor.rowcount
            conn.commit()
            print(f"Updated consent status, rows affected: {rows_affected}")
            
            # Send thank you message
            thank_you_msg = "Thank you for consenting! You'll receive survey links occasionally. Reply STOP anytime to unsubscribe."
            send_result = send_sms(from_number, thank_you_msg)
            print(f"Sent thank you message: {send_result}")
            
        elif message_upper in ["NO", "STOP"]:
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'declined' WHERE phone_number = ?",
                (stored_number,)
            )
            conn.commit()
            
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
                    (email, stored_number)
                )
                conn.commit()
                
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
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def normalize_phone_number(phone):
    """
    Normalize phone number to a consistent format
    Handles cases where carrier might add or remove country code
    """
    # Remove any non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Handle North American numbers (assuming this is for NA market)
    if len(digits_only) == 10:
        # Add US/Canada country code if 10 digits
        return "+1" + digits_only
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        # Add + if it's a standard NA format with country code
        return "+" + digits_only
    elif digits_only.startswith('+'):
        # Already has + prefix
        return phone
    else:
        # Return as is if we can't normalize it
        return phone

def send_consent_request(phone_numbers):
    """Send consent request to list of phone numbers"""
    consent_message = (
        "Hi! This is Pallas Data. You previously expressed interest in participating in our surveys. "
        "We'd like to text you survey links occasionally. "
        "Reply 'YES' to consent or 'NO' to opt out. "
        "You can also reply with your email address if you want to also get surveys emailed to you. "
        "Thanks!"
    )
    
    results = {"success": [], "failed": []}
    
    for phone in phone_numbers:
        # Clean phone number
        phone = phone.strip()
        if not phone:
            continue
            
        # Validate phone number format
        if not is_valid_phone_number(phone):
            results["failed"].append({"phone": phone, "reason": "Invalid phone number format"})
            continue
        
        # Note: We don't need to add to database here anymore since it's already handled
        # by store_participants_with_data function when processing CSV
        
        # Send SMS
        if send_sms(phone, consent_message):
            results["success"].append(phone)
        else:
            results["failed"].append({"phone": phone, "reason": "Failed to send SMS"})
        
        # Add small delay for rate limiting
        import time
        time.sleep(1)
    
    return results

def is_valid_phone_number(phone):
    """
    Basic validation for phone numbers
    Accepts formats like: +1234567890, 1234567890, etc.
    """
    # Remove spaces, dashes, and parentheses
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # If it's just digits and the right length for a phone number, accept it
    if clean_phone.isdigit():
        # 10 digits is a standard North American number
        if len(clean_phone) == 10:
            return True
        # 11 digits with a leading 1 is also a standard NA number
        if len(clean_phone) == 11 and clean_phone.startswith('1'):
            return True
        # Some international numbers might be longer
        if 8 <= len(clean_phone) <= 15:
            return True
    
    # Check if it's a valid international format (starting with +)
    if clean_phone.startswith('+'):
        return re.match(r'^\+\d{10,15}$', clean_phone) is not None
    
    # Default to False for anything else
    return False

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

def process_csv_file(file_content):
    """Process CSV file content and extract phone numbers with additional data"""
    try:
        # Try to decode the file content as UTF-8
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        print("CSV DEBUGGING: File content decoded successfully")
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Try to read the CSV file
        reader = csv.DictReader(csv_file)
        
        # Get all rows
        rows = list(reader)
        
        print(f"CSV DEBUGGING: CSV has {len(rows)} rows")
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # Get column names from the CSV
        fieldnames = reader.fieldnames
        print(f"CSV DEBUGGING: Available columns: {fieldnames}")
        
        # Look for phone number column
        phone_column = None
        for field in fieldnames:
            field_lower = field.lower().strip()
            if field_lower == 'phone_number' or any(keyword in field_lower for keyword in ['phone', 'mobile', 'cell', 'contact', 'number', 'tel']):
                phone_column = field
                print(f"CSV DEBUGGING: Found phone column: '{field}'")
                break
        
        if not phone_column:
            # Use first column as default
            phone_column = fieldnames[0]
            print(f"CSV DEBUGGING: Using first column as phone column: '{phone_column}'")
        
        # Process each row
        processed_data = []
        valid_phones_found = 0
        invalid_phones_found = 0
        
        # Create mapping from CSV columns to database columns
        column_mapping = {
            'calltime': ['calltime', 'call_time', 'call time'],
            'last_fed_vote_intent': ['lastfedvoteintent', 'last_fed_vote_intent', 'vote_intent', 'voting_intent'],
            'gender': ['gender'],
            'age': ['age'],
            'education': ['education'],
            'phone_type': ['phonetype', 'phone_type', 'phone type'],
            'region': ['region'],
            'notes': ['notes', 'note', 'comments']
        }
        
        for row_idx, row in enumerate(rows):
            phone_value = str(row.get(phone_column, '')).strip()
            
            if not phone_value or not is_valid_phone_number(phone_value):
                print(f"CSV DEBUGGING: Row {row_idx}: Invalid phone number '{phone_value}'")
                invalid_phones_found += 1
                continue
            
            normalized_phone = normalize_phone_number(phone_value)
            print(f"CSV DEBUGGING: Row {row_idx}: Valid phone number '{normalized_phone}'")
            
            # Extract additional data
            participant_data = {'phone_number': normalized_phone}
            
            # Map CSV columns to database columns
            for db_column, csv_variations in column_mapping.items():
                value = None
                for csv_col in csv_variations:
                    # Try exact match first
                    if csv_col in row:
                        value = str(row[csv_col]).strip()
                        break
                    # Try case-insensitive match
                    for actual_col in fieldnames:
                        if actual_col.lower() == csv_col.lower():
                            value = str(row[actual_col]).strip()
                            break
                    if value:
                        break
                
                if value and value.lower() not in ['', 'null', 'none', 'n/a']:
                    participant_data[db_column] = value
            
            processed_data.append(participant_data)
            valid_phones_found += 1
        
        print(f"CSV DEBUGGING: Found {valid_phones_found} valid and {invalid_phones_found} invalid phone numbers")
        
        # Remove duplicates while preserving order
        unique_data = []
        seen_phones = set()
        for data in processed_data:
            phone = data['phone_number']
            if phone not in seen_phones:
                seen_phones.add(phone)
                unique_data.append(data)
        
        print(f"CSV DEBUGGING: Returning {len(unique_data)} unique participants with data")
        
        return {
            "status": "success", 
            "participants_data": unique_data,
            "total": len(unique_data)
        }
    
    except Exception as e:
        print(f"CSV DEBUGGING ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def store_participants_with_data(participants_data):
    """Store participants with their additional data in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    results = {"success": [], "failed": []}
    
    try:
        for participant in participants_data:
            phone = participant['phone_number']
            
            # Prepare the update/insert query
            columns = ['phone_number']
            values = [phone]
            placeholders = ['?']
            
            # Add additional columns if they exist
            additional_fields = ['calltime', 'last_fed_vote_intent', 'gender', 'age', 'education', 'phone_type', 'region', 'notes']
            
            for field in additional_fields:
                if field in participant and participant[field]:
                    columns.append(field)
                    values.append(participant[field])
                    placeholders.append('?')
            
            # Create the INSERT OR REPLACE query
            query = f"""
                INSERT OR REPLACE INTO participants 
                ({', '.join(columns)}, created_at) 
                VALUES ({', '.join(placeholders)}, COALESCE(
                    (SELECT created_at FROM participants WHERE phone_number = ?),
                    CURRENT_TIMESTAMP
                ))
            """
            
            try:
                cursor.execute(query, values + [phone])
                results["success"].append(phone)
                print(f"Successfully stored participant: {phone}")
            except Exception as e:
                results["failed"].append({"phone": phone, "reason": f"Database error: {str(e)}"})
                print(f"Failed to store participant {phone}: {str(e)}")
        
        conn.commit()
        
    except Exception as e:
        print(f"Error in store_participants_with_data: {str(e)}")
        results["failed"].append({"phone": "unknown", "reason": f"General error: {str(e)}"})
    finally:
        conn.close()
    
    return results

def search_participants(filters=None):
    """
    Search participants based on various filters
    Returns participants matching the criteria
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Base query - only consented participants
    base_query = """
        SELECT phone_number, consent_status, email, calltime, last_fed_vote_intent, 
               gender, age, education, phone_type, region, notes, survey_sent, created_at
        FROM participants 
        WHERE consent_status = 'consented'
    """
    
    conditions = []
    params = []
    
    if filters:
        # Gender filter
        if filters.get('gender'):
            conditions.append("LOWER(gender) = LOWER(?)")
            params.append(filters['gender'])
        
        # Age filter (can be range or specific)
        if filters.get('age_min'):
            # Handle age as number for range queries
            conditions.append("CAST(age AS INTEGER) >= ?")
            params.append(int(filters['age_min']))
        
        if filters.get('age_max'):
            conditions.append("CAST(age AS INTEGER) <= ?")
            params.append(int(filters['age_max']))
        
        if filters.get('age_exact'):
            conditions.append("age = ?")
            params.append(filters['age_exact'])
        
        # Region filter
        if filters.get('region'):
            conditions.append("LOWER(region) LIKE LOWER(?)")
            params.append(f"%{filters['region']}%")
        
        # Education filter
        if filters.get('education'):
            conditions.append("LOWER(education) LIKE LOWER(?)")
            params.append(f"%{filters['education']}%")
        
        # Phone type filter
        if filters.get('phone_type'):
            conditions.append("LOWER(phone_type) = LOWER(?)")
            params.append(filters['phone_type'])
        
        # Vote intent filter
        if filters.get('vote_intent'):
            conditions.append("LOWER(last_fed_vote_intent) LIKE LOWER(?)")
            params.append(f"%{filters['vote_intent']}%")
        
        # Email filter (has email or not)
        if filters.get('has_email') is not None:
            if filters['has_email']:
                conditions.append("email IS NOT NULL AND email != ''")
            else:
                conditions.append("(email IS NULL OR email = '')")
        
        # Survey sent filter
        if filters.get('survey_sent') is not None:
            conditions.append("survey_sent = ?")
            params.append(1 if filters['survey_sent'] else 0)
        
        # Date range filter
        if filters.get('created_after'):
            conditions.append("created_at >= ?")
            params.append(filters['created_after'])
        
        if filters.get('created_before'):
            conditions.append("created_at <= ?")
            params.append(filters['created_before'])
    
    # Combine conditions
    if conditions:
        query = base_query + " AND " + " AND ".join(conditions)
    else:
        query = base_query
    
    query += " ORDER BY created_at DESC"
    
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        # Create list of dictionaries
        participants = []
        for row in rows:
            participant = {}
            for i, value in enumerate(row):
                participant[column_names[i]] = value
            participants.append(participant)
        
        return {
            "status": "success",
            "participants": participants,
            "count": len(participants)
        }
        
    except Exception as e:
        print(f"Error searching participants: {e}")
        return {
            "status": "error",
            "message": str(e),
            "participants": [],
            "count": 0
        }
    finally:
        conn.close()

def send_targeted_survey(survey_url, phone_numbers, custom_message=None):
    """Send survey link to specific phone numbers"""
    if not phone_numbers:
        return {"status": "error", "message": "No phone numbers provided"}
    
    # Format the message properly - ALWAYS include the survey URL
    if custom_message:
        # If custom message provided, append the survey URL
        message = f"{custom_message.strip()} {survey_url}"
    else:
        # Default message with survey URL
        message = f"Hi! Here's your survey link: {survey_url} Thank you for participating!"
    
    results = {"success": [], "failed": []}
    
    for phone in phone_numbers:
        if send_sms(phone, message):
            results["success"].append(phone)
            
            # Mark as survey sent
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE participants SET survey_sent = 1 WHERE phone_number = ?",
                    (phone,)
                )
                conn.commit()
            except Exception as e:
                print(f"Error updating survey_sent status for {phone}: {e}")
            finally:
                conn.close()
        else:
            results["failed"].append({"phone": phone, "reason": "Failed to send SMS"})
        
        import time
        time.sleep(1)  # Rate limiting
    
    return results

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
    
    # Format the message properly - ALWAYS include the survey URL
    if custom_message:
        # If custom message provided, append the survey URL
        message = f"{custom_message.strip()} {survey_url}"
    else:
        # Default message with survey URL
        message = f"Hi! Here's your survey link: {survey_url} Thank you for participating!"
    
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

def get_filter_options():
    """Get available filter options from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get unique values for dropdown options
        filter_options = {}
        
        # Gender options
        cursor.execute("SELECT DISTINCT gender FROM participants WHERE gender IS NOT NULL AND gender != '' ORDER BY gender")
        filter_options['genders'] = [row[0] for row in cursor.fetchall()]
        
        # Region options
        cursor.execute("SELECT DISTINCT region FROM participants WHERE region IS NOT NULL AND region != '' ORDER BY region")
        filter_options['regions'] = [row[0] for row in cursor.fetchall()]
        
        # Education options
        cursor.execute("SELECT DISTINCT education FROM participants WHERE education IS NOT NULL AND education != '' ORDER BY education")
        filter_options['education_levels'] = [row[0] for row in cursor.fetchall()]
        
        # Phone type options
        cursor.execute("SELECT DISTINCT phone_type FROM participants WHERE phone_type IS NOT NULL AND phone_type != '' ORDER BY phone_type")
        filter_options['phone_types'] = [row[0] for row in cursor.fetchall()]
        
        # Vote intent options
        cursor.execute("SELECT DISTINCT last_fed_vote_intent FROM participants WHERE last_fed_vote_intent IS NOT NULL AND last_fed_vote_intent != '' ORDER BY last_fed_vote_intent")
        filter_options['vote_intents'] = [row[0] for row in cursor.fetchall()]
        
        # Age range
        cursor.execute("SELECT MIN(CAST(age AS INTEGER)), MAX(CAST(age AS INTEGER)) FROM participants WHERE age IS NOT NULL AND age != '' AND age GLOB '[0-9]*'")
        age_range = cursor.fetchone()
        filter_options['age_range'] = {
            'min': age_range[0] if age_range[0] else 18,
            'max': age_range[1] if age_range[1] else 100
        }
        
        return {
            "status": "success",
            "options": filter_options
        }
        
    except Exception as e:
        print(f"Error getting filter options: {e}")
        return {
            "status": "error",
            "message": str(e),
            "options": {}
        }
    finally:
        conn.close()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Twilio webhook"""
    print(f"=== Webhook called at {datetime.now()} ===")
    print(f"Request form data: {request.form}")
    
    # Twilio sends the phone number in the 'From' field
    from_number = request.form.get('From')
    message_body = request.form.get('Body', '').strip()
    
    print(f"From: {from_number}")
    print(f"Message: {message_body}")
    
    # Check if participant exists in database
    if from_number and message_body:
        # Process the response
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
        
        results = send_consent_request([phone_number])
        if phone_number in results["success"]:
            return {'status': 'success', 'message': f'Consent request sent to {phone_number}'}
        else:
            failed_entry = next((entry for entry in results["failed"] if entry["phone"] == phone_number), None)
            reason = failed_entry["reason"] if failed_entry else "Unknown error"
            return {'status': 'error', 'message': f'Failed to send consent request: {reason}'}, 400
    
    return {'status': 'error', 'message': 'Phone number required'}, 400

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV upload and process phone numbers with additional data"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"status": "error", "message": "File must be a CSV"}), 400
    
    try:
        # Read the file content
        file_content = file.read()
        
        # Process the CSV file
        result = process_csv_file(file_content)
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Store participants with their data in the database
        store_results = store_participants_with_data(result["participants_data"])
        
        # Check if we should send consent requests immediately
        send_immediately = request.form.get('send_immediately') == 'true'
        
        if send_immediately and result["participants_data"]:
            # Extract just phone numbers for sending consent requests
            phone_numbers = [p['phone_number'] for p in result["participants_data"]]
            send_results = send_consent_request(phone_numbers)
            
            return jsonify({
                "status": "success",
                "message": f"Processed CSV with additional data and sent consent requests",
                "total_participants": result["total"],
                "stored_successfully": len(store_results["success"]),
                "storage_failures": len(store_results["failed"]),
                "successful_sends": len(send_results["success"]),
                "failed_sends": len(send_results["failed"]),
                "send_failures": send_results["failed"],
                "storage_failures_detail": store_results["failed"]
            })
        
        # Just return the processing results
        return jsonify({
            "status": "success",
            "message": f"Successfully processed CSV and stored {len(store_results['success'])} participants with additional data",
            "total_participants": result["total"],
            "stored_successfully": len(store_results["success"]),
            "storage_failures": len(store_results["failed"]),
            "participants_data": result["participants_data"],  # For preview
            "storage_failures_detail": store_results["failed"]
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500
@app.route('/send_bulk_consent', methods=['POST'])
def send_bulk_consent():
    """Send consent requests to a list of phone numbers"""
    data = request.get_json()
    if not data or 'phone_numbers' not in data or not isinstance(data['phone_numbers'], list):
        return jsonify({"status": "error", "message": "Phone numbers list required"}), 400
    
    phone_numbers = data['phone_numbers']
    if not phone_numbers:
        return jsonify({"status": "error", "message": "Phone numbers list is empty"}), 400
    
    # Send consent requests
    results = send_consent_request(phone_numbers)
    
    return jsonify({
        "status": "success",
        "message": f"Consent requests sent",
        "total_numbers": len(phone_numbers),
        "successful_sends": len(results["success"]),
        "failed_sends": len(results["failed"]),
        "failures": results["failed"]
    })

@app.route('/send_survey', methods=['POST'])
def send_survey_endpoint():
    """Endpoint to send survey link"""
    survey_url = request.form.get('survey_url')
    custom_message = request.form.get('custom_message')
    
    if not survey_url:
        return {'status': 'error', 'message': 'Survey URL required'}, 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get consented participants who haven't been sent this survey
    cursor.execute(
        "SELECT phone_number FROM participants WHERE consent_status = 'consented' AND survey_sent = 0"
    )
    participants = cursor.fetchall()
    conn.close()
    
    if not participants:
        return {'status': 'success', 'message': 'No consented participants found to send survey to'}
    
    # Format the message properly - ALWAYS include the survey URL
    if custom_message and custom_message.strip():
        # If custom message provided, append the survey URL
        message = f"{custom_message.strip()} {survey_url}"
    else:
        # Default message with survey URL
        message = f"Hi! Here's your survey link: {survey_url} Thank you for participating!"
    
    success_count = 0
    failed_count = 0
    
    for (phone,) in participants:
        if send_sms(phone, message):
            success_count += 1
            # Mark as survey sent
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE participants SET survey_sent = 1 WHERE phone_number = ?",
                    (phone,)
                )
                conn.commit()
            except Exception as e:
                print(f"Error updating survey_sent status for {phone}: {e}")
            finally:
                conn.close()
        else:
            failed_count += 1
        
        import time
        time.sleep(1)  # Rate limiting
    
    return {
        'status': 'success', 
        'message': f'Survey sent to {success_count} participants. {failed_count} failed.'
    }
@app.route('/search_participants', methods=['POST'])
def search_participants_endpoint():
    """Search participants based on filters"""
    try:
        data = request.get_json() or {}
        filters = data.get('filters', {})
        
        # Clean up empty filter values
        cleaned_filters = {}
        for key, value in filters.items():
            if value is not None and str(value).strip() != '':
                cleaned_filters[key] = value
        
        result = search_participants(cleaned_filters if cleaned_filters else None)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e),
            "participants": [],
            "count": 0
        }), 500

@app.route('/filter_options', methods=['GET'])
def get_filter_options_endpoint():
    """Get available filter options"""
    try:
        result = get_filter_options()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "options": {}
        }), 500

@app.route('/send_targeted_survey', methods=['POST'])
def send_targeted_survey_endpoint():
    """Send survey to targeted participants"""
    try:
        data = request.get_json()
        
        survey_url = data.get('survey_url')
        phone_numbers = data.get('phone_numbers', [])
        custom_message = data.get('custom_message')
        
        if not survey_url:
            return jsonify({"status": "error", "message": "Survey URL is required"}), 400
        
        if not phone_numbers:
            return jsonify({"status": "error", "message": "No participants selected"}), 400
        
        results = send_targeted_survey(survey_url, phone_numbers, custom_message)
        
        return jsonify({
            "status": "success",
            "message": f"Survey sent to {len(results['success'])} participants",
            "successful_sends": len(results['success']),
            "failed_sends": len(results['failed']),
            "failures": results['failed']
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

@app.route('/export_data', methods=['GET'])
def export_data():
    """Export all data to a CSV file"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all participants
        cursor.execute("SELECT * FROM participants")
        participants = cursor.fetchall()
        participant_columns = [description[0] for description in cursor.description]
        
        # Get all responses
        cursor.execute("SELECT * FROM responses")
        responses = cursor.fetchall()
        response_columns = [description[0] for description in cursor.description]
        
        conn.close()
        
        # Create a CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write participants section
        writer.writerow(['## PARTICIPANTS'])
        writer.writerow(participant_columns)
        for row in participants:
            writer.writerow(row)
        
        # Add a separator
        writer.writerow([])
        writer.writerow(['## RESPONSES'])
        
        # Write responses section
        writer.writerow(response_columns)
        for row in responses:
            writer.writerow(row)
        
        # Prepare response
        output.seek(0)
        csv_data = output.getvalue()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"survey_data_{timestamp}.csv"
        
        # Return the CSV file as a downloadable attachment
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        print(f"Error exporting data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/participants')
def participants():
    """Get all participants with proper error handling"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if participants table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='participants'")
        if not cursor.fetchone():
            return jsonify({
                'status': 'success',
                'data': [],
                'message': 'No participants table found - database may be empty'
            })
        
        cursor.execute("SELECT * FROM participants ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        # Create a list of dictionaries
        participants_list = []
        for row in rows:
            participant_dict = {}
            for i, value in enumerate(row):
                participant_dict[column_names[i]] = value
            participants_list.append(participant_dict)
        
        return jsonify({
            'status': 'success',
            'data': participants_list,
            'count': len(participants_list)
        })
        
    except sqlite3.Error as e:
        print(f"Database error in participants endpoint: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}',
            'data': []
        }), 500
        
    except Exception as e:
        print(f"General error in participants endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}',
            'data': []
        }), 500
        
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
            max-width: 800px;
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
        h2 {
            color: #555;
            margin-top: 20px;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], input[type="url"], textarea, input[type="file"] {
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
            margin-right: 10px;
            margin-bottom: 10px;
        }
        button:hover {
            background-color: #0056b3;
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
        .form-row input {
            flex: 1;
        }
        .checkbox-group {
            margin: 10px 0;
        }
        .checkbox-group label {
            display: inline;
            font-weight: normal;
            margin-left: 5px;
        }
        .preview-area {
            margin-top: 20px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background-color: #f8f9fa;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }
        .preview-header {
            font-weight: bold;
            margin-bottom: 10px;
        }
        .preview-list {
            margin: 0;
            padding-left: 20px;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
            border-bottom: 1px solid #ddd;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            margin-right: 5px;
            border: 1px solid #ddd;
            border-bottom: none;
            border-radius: 5px 5px 0 0;
            background-color: #f8f9fa;
        }
        .tab.active {
            background-color: white;
            border-bottom: 1px solid white;
            margin-bottom: -1px;
            font-weight: bold;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 SMS Management Dashboard</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="openTab(event, 'tab-single')">Single Number</div>
            <div class="tab" onclick="openTab(event, 'tab-csv')">CSV Upload</div>
            <div class="tab" onclick="openTab(event, 'tab-survey')">Send Survey</div>
            <div class="tab" onclick="openTab(event, 'tab-manage')">Manage Data</div>
        </div>
        
        <div id="tab-single" class="tab-content active">
            <div class="section">
                <h2>Send Consent Request to Single Number</h2>
                <div class="form-group">
                    <label for="phone">Phone Number (e.g., +16478941552):</label>
                    <input type="text" id="phone" placeholder="+1234567890">
                </div>
                <button onclick="sendConsent()">Send Consent Request</button>
            </div>
        </div>
        
        <div id="tab-csv" class="tab-content">
            <div class="section">
                <h2>Upload CSV with Phone Numbers</h2>
                <div class="form-group">
                    <label for="csvFile">Select a CSV file with phone numbers:</label>
                    <input type="file" id="csvFile" accept=".csv">
                    <p style="color: #6c757d; font-size: 14px; margin-top: 5px;">
                        The system will look for columns with names containing "phone", "mobile", 
                        "cell", "contact", "number", or "tel". If no matching columns are found, 
                        it will use the first column.
                    </p>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="sendImmediately">
                    <label for="sendImmediately">Send consent requests immediately after upload</label>
                </div>
                <button onclick="uploadCSV()">Upload CSV</button>
                
                <div id="previewArea" class="preview-area">
                    <div class="preview-header">Phone Numbers Preview:</div>
                    <ul id="phonePreview" class="preview-list"></ul>
                    <div id="previewControls" style="margin-top: 15px; display: none;">
                        <button onclick="sendConsentToPreview()">Send Consent Requests to These Numbers</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Enhanced Survey Tab Content -->
<div id="tab-survey" class="tab-content">
    <div class="section">
        <h2>Send Survey Link</h2>
        
        <!-- Survey Details -->
        <div class="form-group">
            <label for="surveyUrl">Survey URL:</label>
            <input type="url" id="surveyUrl" placeholder="https://your-survey-link.com">
        </div>
        <div class="form-group">
            <label for="customMessage">Custom Message (optional):</label>
            <textarea id="customMessage" rows="3" placeholder="Enter a custom message to send with the survey link..."></textarea>
        </div>
        
        <!-- Survey Target Selection -->
        <div style="margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f8f9fa;">
            <h3 style="margin-top: 0;">Target Audience</h3>
            
            <div class="form-row" style="margin-bottom: 15px;">
                <button type="button" onclick="toggleTargetingMode('all')" id="targetAll" class="targeting-btn active">Send to All Consented</button>
                <button type="button" onclick="toggleTargetingMode('search')" id="targetSearch" class="targeting-btn">Search & Filter</button>
            </div>
            
            <!-- Search Interface (Hidden by default) -->
            <div id="searchInterface" style="display: none;">
                <div class="search-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <div class="form-group">
                        <label for="filterGender">Gender:</label>
                        <select id="filterGender">
                            <option value="">Any</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="filterRegion">Region:</label>
                        <select id="filterRegion">
                            <option value="">Any</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="filterEducation">Education:</label>
                        <select id="filterEducation">
                            <option value="">Any</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="filterPhoneType">Phone Type:</label>
                        <select id="filterPhoneType">
                            <option value="">Any</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="filterVoteIntent">Voting Intent:</label>
                        <select id="filterVoteIntent">
                            <option value="">Any</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="filterSurveySent">Survey Status:</label>
                        <select id="filterSurveySent">
                            <option value="">Any</option>
                            <option value="false">Not sent survey</option>
                            <option value="true">Already sent survey</option>
                        </select>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <div class="form-group">
                        <label for="filterAgeMin">Min Age:</label>
                        <input type="number" id="filterAgeMin" placeholder="18" min="18" max="100">
                    </div>
                    
                    <div class="form-group">
                        <label for="filterAgeMax">Max Age:</label>
                        <input type="number" id="filterAgeMax" placeholder="100" min="18" max="100">
                    </div>
                </div>
                
                <div style="text-align: center; margin-bottom: 15px;">
                    <button onclick="searchParticipants()" style="background-color: #17a2b8; margin-right: 10px;">🔍 Search Participants</button>
                    <button onclick="clearFilters()" style="background-color: #6c757d;">Clear Filters</button>
                </div>
                
                <!-- Search Results -->
                <div id="searchResults" style="display: none; margin-top: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin: 0;">Search Results: <span id="resultCount">0</span> participants</h4>
                        <div>
                            <button onclick="selectAllResults()" style="background-color: #28a745; font-size: 12px; padding: 5px 10px;">Select All</button>
                            <button onclick="deselectAllResults()" style="background-color: #dc3545; font-size: 12px; padding: 5px 10px;">Deselect All</button>
                        </div>
                    </div>
                    
                    <div id="participantsList" style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background-color: white; border-radius: 5px;">
                        <!-- Results will be populated here -->
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Action Buttons -->
        <div style="text-align: center; margin-top: 20px;">
            <button onclick="sendSurvey()" id="sendSurveyBtn" style="background-color: #007bff; font-size: 18px; padding: 15px 30px;">📧 Send Survey</button>
        </div>
    </div>
</div>

<style>
.targeting-btn {
    background-color: #6c757d;
    color: white;
    padding: 8px 16px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    margin-right: 10px;
}

.targeting-btn.active {
    background-color: #007bff;
}

.targeting-btn:hover {
    opacity: 0.8;
}

.participant-item {
    padding: 10px;
    margin-bottom: 8px;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
    background-color: #f9f9f9;
    cursor: pointer;
    transition: background-color 0.2s;
}

.participant-item:hover {
    background-color: #e9ecef;
}

.participant-item.selected {
    background-color: #d4edda;
    border-color: #28a745;
}

.participant-item input[type="checkbox"] {
    margin-right: 10px;
}

.participant-main {
    font-weight: bold;
    margin-bottom: 5px;
}

.participant-details {
    font-size: 12px;
    color: #666;
}

.search-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}

@media (max-width: 768px) {
    .search-grid {
        grid-template-columns: 1fr;
    }
}
</style>
        
        <div id="tab-manage" class="tab-content">
            <div class="section">
                <h2>Manage Participants</h2>
                <div style="margin-bottom: 15px;">
                    <button onclick="viewParticipants()">View All Participants</button>
                    <button onclick="exportData()">Export Data to CSV</button>
                </div>
                <div id="participantsTable" style="margin-top: 20px; display: none;">
                    <table id="participantsData" style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="border: 1px solid #ddd; padding: 8px;">Phone Number</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Consent Status</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Email</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Survey Sent</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Additional Data</th>
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
        </div>
        
        <div id="status"></div>
    </div>

    <script>
        const API_BASE = window.location.origin;
        let extractedPhoneNumbers = [];

        function openTab(evt, tabName) {
            // Hide all tab content
            const tabContents = document.getElementsByClassName("tab-content");
            for (let i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove("active");
            }
            
            // Remove active class from all tabs
            const tabs = document.getElementsByClassName("tab");
            for (let i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove("active");
            }
            
            // Show the selected tab content and add active class to the tab
            document.getElementById(tabName).classList.add("active");
            evt.currentTarget.classList.add("active");
        }

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

        async function uploadCSV() {
            const fileInput = document.getElementById('csvFile');
            const sendImmediately = document.getElementById('sendImmediately').checked;
            
            if (!fileInput.files || fileInput.files.length === 0) {
                showStatus('Please select a CSV file', false);
                return;
            }

            const file = fileInput.files[0];
            if (!file.name.endsWith('.csv')) {
                showStatus('Please select a CSV file', false);
                return;
            }

            const formData = new FormData();
            formData.append('file', file);
            formData.append('send_immediately', sendImmediately);

            try {
                const response = await fetch(`${API_BASE}/upload_csv`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    if (sendImmediately) {
                        showStatus(`Successfully sent consent requests to ${result.successful_sends} out of ${result.total_numbers} phone numbers`, true);
                    } else {
                        // Store the extracted phone numbers for later use
                        extractedPhoneNumbers = result.phone_numbers;
                        
                        // Show preview
                        const previewArea = document.getElementById('previewArea');
                        const phonePreview = document.getElementById('phonePreview');
                        const previewControls = document.getElementById('previewControls');
                        
                        // Clear previous preview
                        phonePreview.innerHTML = '';
                        
                        // Add phone numbers to the preview
                        if (extractedPhoneNumbers.length > 0) {
                            extractedPhoneNumbers.forEach(phone => {
                                const li = document.createElement('li');
                                li.textContent = phone;
                                phonePreview.appendChild(li);
                            });
                            
                            previewControls.style.display = 'block';
                        } else {
                            const li = document.createElement('li');
                            li.textContent = 'No valid phone numbers found in the CSV file.';
                            phonePreview.appendChild(li);
                            
                            previewControls.style.display = 'none';
                        }
                        
                        previewArea.style.display = 'block';
                        showStatus(`Successfully extracted ${result.total} phone numbers from CSV`, true);
                    }
                } else {
                    showStatus(result.message || 'Error processing CSV file', false);
                }
                
            } catch (error) {
                showStatus('Error uploading CSV: ' + error.message, false);
            }
        }

        async function sendConsentToPreview() {
            if (!extractedPhoneNumbers || extractedPhoneNumbers.length === 0) {
                showStatus('No phone numbers to send consent requests to', false);
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/send_bulk_consent`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        phone_numbers: extractedPhoneNumbers
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showStatus(`Successfully sent consent requests to ${result.successful_sends} out of ${result.total_numbers} phone numbers`, true);
                } else {
                    showStatus(result.message || 'Error sending consent requests', false);
                }
            } catch (error) {
                showStatus('Error sending consent requests: ' + error.message, false);
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
                            
                            // Add button to view additional data
                            const additionalCell = row.insertCell(4);
                            const viewButton = document.createElement('button');
                            viewButton.textContent = 'View Data';
                            viewButton.style.padding = '5px 10px';
                            viewButton.style.fontSize = '12px';
                            viewButton.onclick = () => showAdditionalData(participant);
                            additionalCell.appendChild(viewButton);
                        });
                    } else {
                        const row = tbody.insertRow();
                        const cell = row.insertCell(0);
                        cell.colSpan = 5;
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
        
        function showAdditionalData(participant) {
            // Create a modal to show additional data
            const modal = document.createElement('div');
            modal.style.position = 'fixed';
            modal.style.top = '0';
            modal.style.left = '0';
            modal.style.width = '100%';
            modal.style.height = '100%';
            modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
            modal.style.display = 'flex';
            modal.style.justifyContent = 'center';
            modal.style.alignItems = 'center';
            modal.style.zIndex = '1000';
            
            const content = document.createElement('div');
            content.style.backgroundColor = 'white';
            content.style.padding = '20px';
            content.style.borderRadius = '5px';
            content.style.width = '80%';
            content.style.maxWidth = '600px';
            content.style.maxHeight = '80%';
            content.style.overflowY = 'auto';
            
            const closeBtn = document.createElement('button');
            closeBtn.textContent = 'Close';
            closeBtn.style.float = 'right';
            closeBtn.onclick = () => document.body.removeChild(modal);
            
            content.innerHTML = `
                <h3>Additional Data for ${participant.phone_number}</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr>
                        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Field</th>
                        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Value</th>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Call Time</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.calltime || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Last Federal Vote Intent</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.last_fed_vote_intent || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Gender</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.gender || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Age</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.age || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Education</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.education || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Phone Type</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.phone_type || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Region</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.region || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Notes</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.notes || 'N/A'}</td>
                    </tr>
                </table>
            `;
            
            content.appendChild(closeBtn);
            modal.appendChild(content);
            document.body.appendChild(modal);
            
            // Close when clicking outside the modal
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                }
            });
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

        function exportData() {
            showStatus('Starting data export...', true);
            
            // Create a hidden iframe to trigger the download without navigating away
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            document.body.appendChild(iframe);
            
            // Set the source to the export endpoint
            iframe.src = `${API_BASE}/export_data`;
            
            // Notify the user
            setTimeout(() => {
                showStatus('Download started. Check your downloads folder.', true);
                
                // Clean up the iframe after download has started
                setTimeout(() => {
                    document.body.removeChild(iframe);
                }, 5000);
            }, 1000);
        }

        // Updated JavaScript functions for the dashboard

let extractedParticipantsData = [];

async function uploadCSV() {
    const fileInput = document.getElementById('csvFile');
    const sendImmediately = document.getElementById('sendImmediately').checked;
    
    if (!fileInput.files || fileInput.files.length === 0) {
        showStatus('Please select a CSV file', false);
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.endsWith('.csv')) {
        showStatus('Please select a CSV file', false);
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('send_immediately', sendImmediately);

    try {
        const response = await fetch(`${API_BASE}/upload_csv`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            if (sendImmediately) {
                showStatus(`Successfully processed ${result.total_participants} participants and sent consent requests to ${result.successful_sends} phone numbers`, true);
            } else {
                // Store the extracted participants data for later use
                extractedParticipantsData = result.participants_data;
                
                // Show enhanced preview
                const previewArea = document.getElementById('previewArea');
                const phonePreview = document.getElementById('phonePreview');
                const previewControls = document.getElementById('previewControls');
                
                // Clear previous preview
                phonePreview.innerHTML = '';
                
                // Add participants to the preview with additional data
                if (extractedParticipantsData.length > 0) {
                    extractedParticipantsData.forEach((participant, index) => {
                        const li = document.createElement('li');
                        li.style.marginBottom = '10px';
                        li.style.padding = '10px';
                        li.style.border = '1px solid #ddd';
                        li.style.borderRadius = '5px';
                        li.style.backgroundColor = '#f9f9f9';
                        
                        let participantInfo = `<strong>${participant.phone_number}</strong>`;
                        
                        // Add additional data if available
                        const additionalFields = ['calltime', 'last_fed_vote_intent', 'gender', 'age', 'education', 'phone_type', 'region', 'notes'];
                        const additionalData = [];
                        
                        additionalFields.forEach(field => {
                            if (participant[field]) {
                                const displayName = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                                additionalData.push(`${displayName}: ${participant[field]}`);
                            }
                        });
                        
                        if (additionalData.length > 0) {
                            participantInfo += `<br><small style="color: #666;">${additionalData.join(', ')}</small>`;
                        }
                        
                        li.innerHTML = participantInfo;
                        phonePreview.appendChild(li);
                    });
                    
                    previewControls.style.display = 'block';
                } else {
                    const li = document.createElement('li');
                    li.textContent = 'No valid phone numbers found in the CSV file.';
                    phonePreview.appendChild(li);
                    
                    previewControls.style.display = 'none';
                }
                
                previewArea.style.display = 'block';
                showStatus(`Successfully processed ${result.total_participants} participants with additional data from CSV`, true);
            }
        } else {
            showStatus(result.message || 'Error processing CSV file', false);
        }
        
    } catch (error) {
        showStatus('Error uploading CSV: ' + error.message, false);
    }
}

async function sendConsentToPreview() {
    if (!extractedParticipantsData || extractedParticipantsData.length === 0) {
        showStatus('No participants to send consent requests to', false);
        return;
    }

    // Extract just the phone numbers
    const phoneNumbers = extractedParticipantsData.map(p => p.phone_number);

    try {
        const response = await fetch(`${API_BASE}/send_bulk_consent`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone_numbers: phoneNumbers
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showStatus(`Successfully sent consent requests to ${result.successful_sends} out of ${result.total_numbers} phone numbers`, true);
        } else {
            showStatus(result.message || 'Error sending consent requests', false);
        }
    } catch (error) {
        showStatus('Error sending consent requests: ' + error.message, false);
    }
}

let currentTargetingMode = 'all';
let searchResults = [];
let selectedParticipants = [];

// Initialize the survey tab
async function initializeSurveyTab() {
    await loadFilterOptions();
}

// Load filter options from the server
async function loadFilterOptions() {
    try {
        const response = await fetch(`${API_BASE}/filter_options`);
        const result = await response.json();
        
        if (result.status === 'success') {
            const options = result.options;
            
            // Populate dropdowns
            populateSelect('filterGender', options.genders);
            populateSelect('filterRegion', options.regions);
            populateSelect('filterEducation', options.education_levels);
            populateSelect('filterPhoneType', options.phone_types);
            populateSelect('filterVoteIntent', options.vote_intents);
            
            // Set age range
            if (options.age_range) {
                document.getElementById('filterAgeMin').placeholder = options.age_range.min.toString();
                document.getElementById('filterAgeMax').placeholder = options.age_range.max.toString();
            }
        }
    } catch (error) {
        console.error('Error loading filter options:', error);
    }
}

function populateSelect(selectId, options) {
    const select = document.getElementById(selectId);
    const currentValue = select.value;
    
    // Clear existing options (except "Any")
    while (select.children.length > 1) {
        select.removeChild(select.lastChild);
    }
    
    // Add new options
    options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option;
        optionElement.textContent = option;
        select.appendChild(optionElement);
    });
    
    // Restore previous selection if it still exists
    if (currentValue && options.includes(currentValue)) {
        select.value = currentValue;
    }
}

function toggleTargetingMode(mode) {
    currentTargetingMode = mode;
    
    const targetAllBtn = document.getElementById('targetAll');
    const targetSearchBtn = document.getElementById('targetSearch');
    const searchInterface = document.getElementById('searchInterface');
    
    if (mode === 'all') {
        targetAllBtn.classList.add('active');
        targetSearchBtn.classList.remove('active');
        searchInterface.style.display = 'none';
    } else {
        targetAllBtn.classList.remove('active');
        targetSearchBtn.classList.add('active');
        searchInterface.style.display = 'block';
    }
    
    updateSendButton();
}

async function searchParticipants() {
    const filters = {
        gender: document.getElementById('filterGender').value,
        region: document.getElementById('filterRegion').value,
        education: document.getElementById('filterEducation').value,
        phone_type: document.getElementById('filterPhoneType').value,
        vote_intent: document.getElementById('filterVoteIntent').value,
        age_min: document.getElementById('filterAgeMin').value,
        age_max: document.getElementById('filterAgeMax').value,
        survey_sent: document.getElementById('filterSurveySent').value === '' ? null : 
                    document.getElementById('filterSurveySent').value === 'true'
    };
    
    try {
        const response = await fetch(`${API_BASE}/search_participants`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filters })
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            searchResults = result.participants;
            displaySearchResults(searchResults);
            showStatus(`Found ${result.count} matching participants`, true);
        } else {
            showStatus('Search failed: ' + result.message, false);
        }
    } catch (error) {
        showStatus('Error searching participants: ' + error.message, false);
    }
}

function displaySearchResults(participants) {
    const resultCount = document.getElementById('resultCount');
    const participantsList = document.getElementById('participantsList');
    const searchResultsDiv = document.getElementById('searchResults');
    
    resultCount.textContent = participants.length;
    participantsList.innerHTML = '';
    
    if (participants.length === 0) {
        participantsList.innerHTML = '<p style="text-align: center; color: #666;">No participants match your search criteria.</p>';
    } else {
        participants.forEach((participant, index) => {
            const div = document.createElement('div');
            div.className = 'participant-item';
            
            // Create checkbox
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `participant_${index}`;
            checkbox.style.marginRight = '10px';
            checkbox.addEventListener('change', function() {
                toggleParticipantSelection(participant.phone_number);
            });
            
            // Create main content div
            const contentDiv = document.createElement('div');
            contentDiv.style.flex = '1';
            contentDiv.style.cursor = 'pointer';
            contentDiv.addEventListener('click', function() {
                checkbox.checked = !checkbox.checked;
                toggleParticipantSelection(participant.phone_number);
            });
            
            // Phone number
            const phoneDiv = document.createElement('div');
            phoneDiv.className = 'participant-main';
            phoneDiv.textContent = participant.phone_number;
            
            // Details
            const details = [];
            if (participant.gender) details.push(`Gender: ${participant.gender}`);
            if (participant.age) details.push(`Age: ${participant.age}`);
            if (participant.region) details.push(`Region: ${participant.region}`);
            if (participant.education) details.push(`Education: ${participant.education}`);
            if (participant.last_fed_vote_intent) details.push(`Vote Intent: ${participant.last_fed_vote_intent}`);
            if (participant.survey_sent) details.push(`Survey: ${participant.survey_sent ? 'Sent' : 'Not sent'}`);
            
            const detailsDiv = document.createElement('div');
            detailsDiv.className = 'participant-details';
            detailsDiv.textContent = details.join(' • ');
            
            // Assemble the structure
            contentDiv.appendChild(phoneDiv);
            contentDiv.appendChild(detailsDiv);
            
            div.style.display = 'flex';
            div.style.alignItems = 'center';
            div.appendChild(checkbox);
            div.appendChild(contentDiv);
            
            participantsList.appendChild(div);
        });
    }
    
    searchResultsDiv.style.display = 'block';
    selectedParticipants = []; // Reset selection
    updateSendButton();
}

function selectAllResults() {
    selectedParticipants = searchResults.map(p => p.phone_number);
    
    const participantItems = document.querySelectorAll('.participant-item');
    participantItems.forEach(item => {
        item.classList.add('selected');
        const checkbox = item.querySelector('input[type="checkbox"]');
        if (checkbox) checkbox.checked = true;
    });
    
    updateSendButton();
}

function deselectAllResults() {
    selectedParticipants = [];
    
    const participantItems = document.querySelectorAll('.participant-item');
    participantItems.forEach(item => {
        item.classList.remove('selected');
        const checkbox = item.querySelector('input[type="checkbox"]');
        if (checkbox) checkbox.checked = false;
    });
    
    updateSendButton();
}

function clearFilters() {
    document.getElementById('filterGender').value = '';
    document.getElementById('filterRegion').value = '';
    document.getElementById('filterEducation').value = '';
    document.getElementById('filterPhoneType').value = '';
    document.getElementById('filterVoteIntent').value = '';
    document.getElementById('filterSurveySent').value = '';
    document.getElementById('filterAgeMin').value = '';
    document.getElementById('filterAgeMax').value = '';
    
    document.getElementById('searchResults').style.display = 'none';
    selectedParticipants = [];
    updateSendButton();
}

function updateSendButton() {
    const sendBtn = document.getElementById('sendSurveyBtn');
    
    if (currentTargetingMode === 'all') {
        sendBtn.textContent = '📧 Send Survey to All Consented';
    } else if (selectedParticipants.length > 0) {
        sendBtn.textContent = `📧 Send Survey to ${selectedParticipants.length} Selected`;
    } else {
        sendBtn.textContent = '📧 Send Survey (No participants selected)';
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
        let response;
        
        if (currentTargetingMode === 'all') {
            // Send to all consented participants (original functionality)
            const body = `survey_url=${encodeURIComponent(surveyUrl)}`;
            const fullBody = customMessage ? 
                `${body}&custom_message=${encodeURIComponent(customMessage)}` : body;
            
            response = await fetch(`${API_BASE}/send_survey`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: fullBody
            });
        } else {
            // Send to selected participants
            if (selectedParticipants.length === 0) {
                showStatus('Please select participants to send the survey to', false);
                return;
            }
            
            response = await fetch(`${API_BASE}/send_targeted_survey`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    survey_url: surveyUrl,
                    phone_numbers: selectedParticipants,
                    custom_message: customMessage
                })
            });
        }
        
        const result = await response.json();
        showStatus(result.message, response.ok);
        
        // Refresh search results if we were in search mode
        if (currentTargetingMode === 'search' && selectedParticipants.length > 0) {
            setTimeout(() => {
                searchParticipants(); // Refresh to show updated survey_sent status
            }, 1000);
        }
        
    } catch (error) {
        showStatus('Error sending survey: ' + error.message, false);
    }
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize survey tab when it becomes active
    const surveyTab = document.querySelector('[onclick*="tab-survey"]');
    if (surveyTab) {
        surveyTab.addEventListener('click', initializeSurveyTab);
    }
    
    // Also initialize if survey tab is already active
    if (document.getElementById('tab-survey').classList.contains('active')) {
        initializeSurveyTab();
    }
});
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
