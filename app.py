@app.route('/column_definitions', methods=['GET'])
def get_column_definitions_route():
    """Get all column definitions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, column_name, display_name, data_type, is_active FROM csv_columns")
        columns = cursor.fetchall()
        
        column_list = []
        for col in columns:
            column_list.append({
                "id": col[0],
                "column_name": col[1],
                "display_name": col[2],
                "data_type": col[3],
                "is_active": bool(col[4])
            })
        
        return jsonify({
            "status": "success",
            "columns": column_list
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/toggle_column', methods=['POST'])
def toggle_column():
    """Toggle a column's active status"""
    data = request.get_json()
    
    if not data or 'column_id' not in data:
        return jsonify({"status": "error", "message": "Column ID required"}), 400
    
    column_id = data['column_id']
    is_active = data.get('is_active', True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE csv_columns SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, column_id)
        )
        conn.commit()
        
        # Ensure columns are updated in the database
        ensure_dynamic_columns()
        
        return jsonify({
            "status": "success",
            "message": f"Column status updated successfully"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/add_column', methods=['POST'])
def add_column():
    """Add a new custom column definition"""
    data = request.get_json()
    
    if not data or 'column_name' not in data:
        return jsonify({"status": "error", "message": "Column name required"}), 400
    
    column_name = data['column_name'].lower().replace(' ', '_')
    display_name = data.get('display_name', None)
    data_type = data.get('data_type', 'TEXT')
    
    # Validate column name (only allow alphanumeric and underscore)
    if not re.match(r'^[a-z0-9_]+import os
import sqlite3
import re
import csv
import io
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, Response, session
import requests

# Initialize Flask app
app = Flask(__name__)

# Database path
DB_PATH = "survey_responses.db"

def init_database():
    """Initialize database with required tables and dynamic column handling"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create participants table with essential columns only
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
    
    # Create metadata table to store column definitions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csv_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_name TEXT UNIQUE,
            display_name TEXT,
            data_type TEXT DEFAULT 'TEXT',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Ensure dynamic columns exist in the participants table
    ensure_dynamic_columns()

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
        
        # Phone number is valid, so proceed
        normalized_phone = normalize_phone_number(phone)
        
        # Add to database - this will now be handled by the CSV processing function
        # to include the additional fields
        
        # Send SMS
        if send_sms(normalized_phone, consent_message):
            results["success"].append(normalized_phone)
        else:
            results["failed"].append({"phone": normalized_phone, "reason": "Failed to send SMS"})
        
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
    
    # Check if it's a valid international format (starting with +)
    if clean_phone.startswith('+'):
        return re.match(r'^\+\d{10,15}$', clean_phone) is not None
    
    # Check if it's a valid US/CA format (10 digits, optionally starting with 1)
    return re.match(r'^1?\d{10}$', clean_phone) is not None

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
    """Process CSV file content, detect columns, and return structure for column selection"""
    try:
        # Try to decode the file content as UTF-8
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Try to read the CSV file
        reader = csv.reader(csv_file)
        
        # Get all rows
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # First row is assumed to be header
        headers = [h.strip() for h in rows[0]]
        
        # Create preview data for column selection
        preview_data = []
        for i in range(1, min(6, len(rows))):  # Preview first 5 rows
            if i < len(rows):
                row_data = {}
                for j, header in enumerate(headers):
                    if j < len(rows[i]):
                        row_data[header] = rows[i][j]
                    else:
                        row_data[header] = ""
                preview_data.append(row_data)
        
        # Identify phone number column
        phone_column = None
        for header in headers:
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['phone', 'mobile', 'cell', 'contact', 'number', 'tel']):
                phone_column = header
                break
        
        # If no phone column found, guess it's the first column
        if not phone_column and headers:
            phone_column = headers[0]
        
        return {
            "status": "success",
            "headers": headers,
            "phone_column": phone_column,
            "preview_data": preview_data,
            "total_rows": len(rows) - 1  # Exclude header row
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_selected_csv_data(file_content, phone_column, selected_columns):
    """Save data from CSV based on selected columns"""
    try:
        # Decode the file content
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Read the CSV file
        reader = csv.reader(csv_file)
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # Get headers and their indices
        headers = [h.strip() for h in rows[0]]
        column_indices = {}
        
        # Map selected column names to their indices
        for col in selected_columns:
            if col in headers:
                column_indices[col] = headers.index(col)
        
        # Get phone column index
        if phone_column not in headers:
            return {"status": "error", "message": f"Phone column '{phone_column}' not found in CSV"}
        
        phone_idx = headers.index(phone_column)
        
        # Process each row and extract data
        processed_data = []
        for row in rows[1:]:  # Skip header row
            if len(row) <= phone_idx or not row[phone_idx].strip():
                continue  # Skip rows with no phone number
                
            phone = row[phone_idx].strip()
            if not is_valid_phone_number(phone):
                continue  # Skip invalid phone numbers
            
            # Create data entry with phone number
            entry = {"phone": normalize_phone_number(phone)}
            
            # Add selected column data
            for col_name, col_idx in column_indices.items():
                if col_idx < len(row):
                    # Convert column name to snake_case for database storage
                    db_col_name = col_name.lower().replace(' ', '_')
                    entry[db_col_name] = row[col_idx].strip()
                    
                    # Add column definition if it doesn't exist
                    add_column_definition(db_col_name, col_name)
            
            processed_data.append(entry)
        
        # Save data to database
        save_data_to_db(processed_data)
        
        # Return just the phone numbers for consent sending
        phone_numbers = [entry["phone"] for entry in processed_data]
        
        # Remove duplicates while preserving order
        unique_phones = []
        seen = set()
        for phone in phone_numbers:
            if phone not in seen:
                seen.add(phone)
                unique_phones.append(phone)
                
        return {
            "status": "success", 
            "phone_numbers": unique_phones,
            "total": len(unique_phones)
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_data_to_db(data_entries):
    """Save all data entries to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for entry in data_entries:
        try:
            # Get the phone number
            phone = entry.pop("phone")
            
            # Check if phone number already exists
            cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (phone,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entry with new data
                update_parts = []
                update_values = []
                
                for key, value in entry.items():
                    update_parts.append(f"{key} = ?")
                    update_values.append(value)
                
                # Only proceed if there are fields to update
                if update_parts:
                    update_values.append(phone)  # Add phone number for WHERE clause
                    update_sql = f"UPDATE participants SET {', '.join(update_parts)} WHERE phone_number = ?"
                    cursor.execute(update_sql, update_values)
            else:
                # Insert new entry
                columns = ["phone_number"] + list(entry.keys())
                placeholders = ["?"] * len(columns)
                values = [phone] + list(entry.values())
                
                insert_sql = f"INSERT INTO participants ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(insert_sql, values)
        except Exception as e:
            print(f"Error saving entry for {phone}: {e}")
            
    conn.commit()
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
        normalized_phone = normalize_phone_number(phone_number)
        
        # Send the consent message
        results = send_consent_request([normalized_phone])
        if normalized_phone in results["success"]:
            return {'status': 'success', 'message': f'Consent request sent to {normalized_phone}'}
        else:
            failed_entry = next((entry for entry in results["failed"] if entry["phone"] == normalized_phone), None)
            reason = failed_entry["reason"] if failed_entry else "Unknown error"
            return {'status': 'error', 'message': f'Failed to send consent request: {reason}'}, 400
    
    return {'status': 'error', 'message': 'Phone number required'}, 400

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV upload and process structure for column selection"""
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
        
        # Store file content in session for later use
        session_id = str(uuid.uuid4())
        temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)
        
        # Process the CSV file to get structure
        result = process_csv_file(file_content)
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Return the CSV structure for column selection
        return jsonify({
            "status": "success",
            "message": "CSV uploaded successfully. Please select columns to import.",
            "session_id": session_id,
            "headers": result["headers"],
            "phone_column": result["phone_column"],
            "preview_data": result["preview_data"],
            "total_rows": result["total_rows"]
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500

@app.route('/process_selected_columns', methods=['POST'])
def process_selected_columns():
    """Process CSV data based on selected columns"""
    data = request.get_json()
    
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    session_id = data.get('session_id')
    phone_column = data.get('phone_column')
    selected_columns = data.get('selected_columns', [])
    send_consent = data.get('send_consent', False)
    
    if not session_id or not phone_column:
        return jsonify({"status": "error", "message": "Missing required parameters"}), 400
    
    # Load the CSV file from temporary storage
    temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
    
    if not os.path.exists(temp_file_path):
        return jsonify({"status": "error", "message": "CSV file not found. Please upload again."}), 400
    
    try:
        with open(temp_file_path, 'rb') as f:
            file_content = f.read()
        
        # Process the selected columns
        result = save_selected_csv_data(file_content, phone_column, selected_columns)
        
        # Clean up the temporary file
        try:
            os.remove(temp_file_path)
        except:
            pass
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Send consent messages if requested
        if send_consent and result["phone_numbers"]:
            send_results = send_consent_request(result["phone_numbers"])
            
            return jsonify({
                "status": "success",
                "message": f"Processed CSV and sent consent requests",
                "total_numbers": result["total"],
                "selected_columns": selected_columns,
                "successful_sends": len(send_results["success"]),
                "failed_sends": len(send_results["failed"]),
                "failures": send_results["failed"]
            })
        
        # Return the results
        return jsonify({
            "status": "success",
            "message": f"Successfully saved data for {result['total']} participants",
            "selected_columns": selected_columns,
            "phone_numbers": result["phone_numbers"],
            "total": result["total"]
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error processing selected columns: {str(e)}"}), 500

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
    """Get all participants with dynamic column support"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants")
    rows = cursor.fetchall()
    
    # Get column names dynamically
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
        'data': participants_list,
        'columns': column_names
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
        }, column_name):
        return jsonify({"status": "error", "message": "Column name can only contain lowercase letters, numbers, and underscores"}), 400
    
    # Add the column definition
    if add_column_definition(column_name, display_name, data_type):
        return jsonify({
            "status": "success", 
            "message": f"Column '{column_name}' added successfully"
        })
    else:
        return jsonify({
            "status": "error", 
            "message": f"Column '{column_name}' already exists or could not be added"
        }), 400import os
import sqlite3
import re
import csv
import io
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, Response, session
import requests

# Initialize Flask app
app = Flask(__name__)

# Database path
DB_PATH = "survey_responses.db"

def init_database():
    """Initialize database with required tables and dynamic column handling"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create participants table with essential columns only
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
    
    # Create metadata table to store column definitions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csv_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_name TEXT UNIQUE,
            display_name TEXT,
            data_type TEXT DEFAULT 'TEXT',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Ensure dynamic columns exist in the participants table
    ensure_dynamic_columns()

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
        
        # Phone number is valid, so proceed
        normalized_phone = normalize_phone_number(phone)
        
        # Add to database - this will now be handled by the CSV processing function
        # to include the additional fields
        
        # Send SMS
        if send_sms(normalized_phone, consent_message):
            results["success"].append(normalized_phone)
        else:
            results["failed"].append({"phone": normalized_phone, "reason": "Failed to send SMS"})
        
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
    
    # Check if it's a valid international format (starting with +)
    if clean_phone.startswith('+'):
        return re.match(r'^\+\d{10,15}$', clean_phone) is not None
    
    # Check if it's a valid US/CA format (10 digits, optionally starting with 1)
    return re.match(r'^1?\d{10}$', clean_phone) is not None

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
    """Process CSV file content, detect columns, and return structure for column selection"""
    try:
        # Try to decode the file content as UTF-8
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Try to read the CSV file
        reader = csv.reader(csv_file)
        
        # Get all rows
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # First row is assumed to be header
        headers = [h.strip() for h in rows[0]]
        
        # Create preview data for column selection
        preview_data = []
        for i in range(1, min(6, len(rows))):  # Preview first 5 rows
            if i < len(rows):
                row_data = {}
                for j, header in enumerate(headers):
                    if j < len(rows[i]):
                        row_data[header] = rows[i][j]
                    else:
                        row_data[header] = ""
                preview_data.append(row_data)
        
        # Identify phone number column
        phone_column = None
        for header in headers:
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['phone', 'mobile', 'cell', 'contact', 'number', 'tel']):
                phone_column = header
                break
        
        # If no phone column found, guess it's the first column
        if not phone_column and headers:
            phone_column = headers[0]
        
        return {
            "status": "success",
            "headers": headers,
            "phone_column": phone_column,
            "preview_data": preview_data,
            "total_rows": len(rows) - 1  # Exclude header row
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_selected_csv_data(file_content, phone_column, selected_columns):
    """Save data from CSV based on selected columns"""
    try:
        # Decode the file content
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Read the CSV file
        reader = csv.reader(csv_file)
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # Get headers and their indices
        headers = [h.strip() for h in rows[0]]
        column_indices = {}
        
        # Map selected column names to their indices
        for col in selected_columns:
            if col in headers:
                column_indices[col] = headers.index(col)
        
        # Get phone column index
        if phone_column not in headers:
            return {"status": "error", "message": f"Phone column '{phone_column}' not found in CSV"}
        
        phone_idx = headers.index(phone_column)
        
        # Process each row and extract data
        processed_data = []
        for row in rows[1:]:  # Skip header row
            if len(row) <= phone_idx or not row[phone_idx].strip():
                continue  # Skip rows with no phone number
                
            phone = row[phone_idx].strip()
            if not is_valid_phone_number(phone):
                continue  # Skip invalid phone numbers
            
            # Create data entry with phone number
            entry = {"phone": normalize_phone_number(phone)}
            
            # Add selected column data
            for col_name, col_idx in column_indices.items():
                if col_idx < len(row):
                    # Convert column name to snake_case for database storage
                    db_col_name = col_name.lower().replace(' ', '_')
                    entry[db_col_name] = row[col_idx].strip()
                    
                    # Add column definition if it doesn't exist
                    add_column_definition(db_col_name, col_name)
            
            processed_data.append(entry)
        
        # Save data to database
        save_data_to_db(processed_data)
        
        # Return just the phone numbers for consent sending
        phone_numbers = [entry["phone"] for entry in processed_data]
        
        # Remove duplicates while preserving order
        unique_phones = []
        seen = set()
        for phone in phone_numbers:
            if phone not in seen:
                seen.add(phone)
                unique_phones.append(phone)
                
        return {
            "status": "success", 
            "phone_numbers": unique_phones,
            "total": len(unique_phones)
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_data_to_db(data_entries):
    """Save all data entries to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for entry in data_entries:
        try:
            # Get the phone number
            phone = entry.pop("phone")
            
            # Check if phone number already exists
            cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (phone,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entry with new data
                update_parts = []
                update_values = []
                
                for key, value in entry.items():
                    update_parts.append(f"{key} = ?")
                    update_values.append(value)
                
                # Only proceed if there are fields to update
                if update_parts:
                    update_values.append(phone)  # Add phone number for WHERE clause
                    update_sql = f"UPDATE participants SET {', '.join(update_parts)} WHERE phone_number = ?"
                    cursor.execute(update_sql, update_values)
            else:
                # Insert new entry
                columns = ["phone_number"] + list(entry.keys())
                placeholders = ["?"] * len(columns)
                values = [phone] + list(entry.values())
                
                insert_sql = f"INSERT INTO participants ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(insert_sql, values)
        except Exception as e:
            print(f"Error saving entry for {phone}: {e}")
            
    conn.commit()
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
        normalized_phone = normalize_phone_number(phone_number)
        
        # Send the consent message
        results = send_consent_request([normalized_phone])
        if normalized_phone in results["success"]:
            return {'status': 'success', 'message': f'Consent request sent to {normalized_phone}'}
        else:
            failed_entry = next((entry for entry in results["failed"] if entry["phone"] == normalized_phone), None)
            reason = failed_entry["reason"] if failed_entry else "Unknown error"
            return {'status': 'error', 'message': f'Failed to send consent request: {reason}'}, 400
    
    return {'status': 'error', 'message': 'Phone number required'}, 400

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV upload and process structure for column selection"""
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
        
        # Store file content in session for later use
        session_id = str(uuid.uuid4())
        temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)
        
        # Process the CSV file to get structure
        result = process_csv_file(file_content)
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Return the CSV structure for column selection
        return jsonify({
            "status": "success",
            "message": "CSV uploaded successfully. Please select columns to import.",
            "session_id": session_id,
            "headers": result["headers"],
            "phone_column": result["phone_column"],
            "preview_data": result["preview_data"],
            "total_rows": result["total_rows"]
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500

@app.route('/process_selected_columns', methods=['POST'])
def process_selected_columns():
    """Process CSV data based on selected columns"""
    data = request.get_json()
    
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    session_id = data.get('session_id')
    phone_column = data.get('phone_column')
    selected_columns = data.get('selected_columns', [])
    send_consent = data.get('send_consent', False)
    
    if not session_id or not phone_column:
        return jsonify({"status": "error", "message": "Missing required parameters"}), 400
    
    # Load the CSV file from temporary storage
    temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
    
    if not os.path.exists(temp_file_path):
        return jsonify({"status": "error", "message": "CSV file not found. Please upload again."}), 400
    
    try:
        with open(temp_file_path, 'rb') as f:
            file_content = f.read()
        
        # Process the selected columns
        result = save_selected_csv_data(file_content, phone_column, selected_columns)
        
        # Clean up the temporary file
        try:
            os.remove(temp_file_path)
        except:
            pass
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Send consent messages if requested
        if send_consent and result["phone_numbers"]:
            send_results = send_consent_request(result["phone_numbers"])
            
            return jsonify({
                "status": "success",
                "message": f"Processed CSV and sent consent requests",
                "total_numbers": result["total"],
                "selected_columns": selected_columns,
                "successful_sends": len(send_results["success"]),
                "failed_sends": len(send_results["failed"]),
                "failures": send_results["failed"]
            })
        
        # Return the results
        return jsonify({
            "status": "success",
            "message": f"Successfully saved data for {result['total']} participants",
            "selected_columns": selected_columns,
            "phone_numbers": result["phone_numbers"],
            "total": result["total"]
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error processing selected columns: {str(e)}"}), 500

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
