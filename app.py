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
        
        # Add to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO participants (phone_number) VALUES (?)",
                (phone,)
            )
            conn.commit()
        except Exception as e:
            results["failed"].append({"phone": phone, "reason": f"Database error: {str(e)}"})
            continue
        finally:
            conn.close()
        
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
    """Process CSV file content and extract phone numbers"""
    try:
        # Try to decode the file content as UTF-8
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        print("CSV DEBUGGING: File content decoded successfully")
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Try to read the CSV file
        reader = csv.reader(csv_file)
        
        # Get all rows
        rows = list(reader)
        
        print(f"CSV DEBUGGING: CSV has {len(rows)} rows (including header)")
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # Print the first few rows for debugging
        print("CSV DEBUGGING: First 2 rows:")
        for i, row in enumerate(rows[:2]):
            print(f"  Row {i}: {row}")
        
        # Extract phone numbers
        phone_numbers = []
        
        # Check the first row for headers
        first_row = rows[0]
        header_row = True
        
        print(f"CSV DEBUGGING: Headers: {first_row}")
        
        # Look for columns that might contain phone numbers
        phone_col_indices = []
        for i, header in enumerate(first_row):
            header_lower = header.lower().strip()
            print(f"CSV DEBUGGING: Checking header '{header}' (lower: '{header_lower}')")
            if header_lower == 'phone_number' or any(keyword in header_lower for keyword in ['phone', 'mobile', 'cell', 'contact', 'number', 'tel']):
                phone_col_indices.append(i)
                print(f"CSV DEBUGGING: Found potential phone column: '{header}' at index {i}")
        
        # If we couldn't find any phone columns, maybe the first row isn't a header
        if not phone_col_indices:
            print("CSV DEBUGGING: No phone columns found in header row")
            # Check if the first row might contain phone numbers itself
            for i, cell in enumerate(first_row):
                cell_value = str(cell).strip()
                print(f"CSV DEBUGGING: Testing if '{cell_value}' is a valid phone number")
                if cell_value and is_valid_phone_number(cell_value):
                    print(f"CSV DEBUGGING: Found valid phone number in first row: {cell_value}")
                    header_row = False
                    phone_col_indices.append(i)
                    break
        
        # If we still couldn't find phone columns, try the first column
        if not phone_col_indices:
            print("CSV DEBUGGING: Using first column as default phone column")
            phone_col_indices.append(0)
        
        print(f"CSV DEBUGGING: Using columns at indices {phone_col_indices} for phone numbers")
        print(f"CSV DEBUGGING: Treating first row as header: {header_row}")
        
        # Start from the appropriate row (skip header if we identified one)
        start_row = 1 if header_row else 0
        
        # Extract phone numbers from identified columns
        valid_phones_found = 0
        invalid_phones_found = 0
        
        for row_idx, row in enumerate(rows[start_row:], start=start_row):
            phone_found = False
            for col_idx in phone_col_indices:
                if col_idx < len(row):
                    cell_value = str(row[col_idx]).strip()
                    if cell_value:
                        is_valid = is_valid_phone_number(cell_value)
                        print(f"CSV DEBUGGING: Row {row_idx}, Column {col_idx}: '{cell_value}' Valid: {is_valid}")
                        if is_valid:
                            normalized = normalize_phone_number(cell_value)
                            print(f"CSV DEBUGGING: Normalized: {normalized}")
                            phone_numbers.append(normalized)
                            valid_phones_found += 1
                            phone_found = True
                            break
                        else:
                            invalid_phones_found += 1
            
            if not phone_found and row_idx < start_row + 5:  # Only log first few rows to avoid flooding logs
                print(f"CSV DEBUGGING: No valid phone number found in row {row_idx}")
        
        print(f"CSV DEBUGGING: Found {valid_phones_found} valid and {invalid_phones_found} invalid phone numbers")
        
        # Remove duplicates while preserving order
        unique_phones = []
        seen = set()
        for phone in phone_numbers:
            if phone not in seen:
                seen.add(phone)
                unique_phones.append(phone)
        
        print(f"CSV DEBUGGING: Returning {len(unique_phones)} unique phone numbers")
        
        return {
            "status": "success", 
            "phone_numbers": unique_phones,
            "total": len(unique_phones)
        }
    
    except Exception as e:
        print(f"CSV DEBUGGING ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

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
    """Handle CSV upload and process phone numbers"""
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
        
        # Check if we should send consent requests immediately
        send_immediately = request.form.get('send_immediately') == 'true'
        
        if send_immediately and result["phone_numbers"]:
            # Send consent requests to extracted phone numbers
            send_results = send_consent_request(result["phone_numbers"])
            
            return jsonify({
                "status": "success",
                "message": f"Processed CSV and sent consent requests",
                "total_numbers": result["total"],
                "successful_sends": len(send_results["success"]),
                "failed_sends": len(send_results["failed"]),
                "failures": send_results["failed"]
            })
        
        # Just return the extracted phone numbers
        return jsonify({
            "status": "success",
            "message": f"Successfully extracted {result['total']} phone numbers from CSV",
            "phone_numbers": result["phone_numbers"],
            "total": result["total"]
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
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    
    # Create a list of dictionaries
    participants_list = []
    for row in rows:
        participant_dict = {}
        for i, value in enumerate(row):
            participant_dict[column_names[i]] = value
        participants_list.append(participant_dict)
    
    conn.close()
    
    return {
        'status': 'success',
        'data': participants_list
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
        
        <div id="tab-survey" class="tab-content">
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
        </div>
        
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
