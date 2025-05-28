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

def send_mass_sms(phone_numbers, message):
    """Send custom SMS message to a list of phone numbers"""
    if not phone_numbers:
        return {"status": "error", "message": "No phone numbers provided"}
    
    if not message or not message.strip():
        return {"status": "error", "message": "Message cannot be empty"}
    
    results = {"success": [], "failed": []}
    
    for phone in phone_numbers:
        # Clean and validate phone number
        phone = phone.strip()
        if not phone:
            continue
            
        if not is_valid_phone_number(phone):
            results["failed"].append({"phone": phone, "reason": "Invalid phone number format"})
            continue
        
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone)
        
        # Send SMS
        if send_sms(normalized_phone, message.strip()):
            results["success"].append(normalized_phone)
        else:
            results["failed"].append({"phone": normalized_phone, "reason": "Failed to send SMS"})
        
        # Add small delay for rate limiting
        import time
        time.sleep(1)
    
    return results

def process_mass_sms_csv(file_content):
    """Process CSV file for mass SMS (extract phone numbers only)"""
    try:
        # Try to decode the file content as UTF-8
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        print("MASS SMS CSV DEBUGGING: File content decoded successfully")
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Try to read the CSV file
        reader = csv.reader(csv_file)
        
        # Get all rows
        rows = list(reader)
        
        print(f"MASS SMS CSV DEBUGGING: CSV has {len(rows)} rows (including header)")
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # Print the first few rows for debugging
        print("MASS SMS CSV DEBUGGING: First 2 rows:")
        for i, row in enumerate(rows[:2]):
            print(f"  Row {i}: {row}")
        
        # Extract phone numbers
        phone_numbers = []
        
        # Check the first row for headers
        first_row = rows[0]
        header_row = True
        
        print(f"MASS SMS CSV DEBUGGING: Headers: {first_row}")
        
        # Look for columns that might contain phone numbers
        phone_col_indices = []
        for i, header in enumerate(first_row):
            header_lower = header.lower().strip()
            print(f"MASS SMS CSV DEBUGGING: Checking header '{header}' (lower: '{header_lower}')")
            if header_lower == 'phone_number' or any(keyword in header_lower for keyword in ['phone', 'mobile', 'cell', 'contact', 'number', 'tel']):
                phone_col_indices.append(i)
                print(f"MASS SMS CSV DEBUGGING: Found potential phone column: '{header}' at index {i}")
        
        # If we couldn't find any phone columns, maybe the first row isn't a header
        if not phone_col_indices:
            print("MASS SMS CSV DEBUGGING: No phone columns found in header row")
            # Check if the first row might contain phone numbers itself
            for i, cell in enumerate(first_row):
                cell_value = str(cell).strip()
                print(f"MASS SMS CSV DEBUGGING: Testing if '{cell_value}' is a valid phone number")
                if cell_value and is_valid_phone_number(cell_value):
                    print(f"MASS SMS CSV DEBUGGING: Found valid phone number in first row: {cell_value}")
                    header_row = False
                    phone_col_indices.append(i)
                    break
        
        # If we still couldn't find phone columns, try the first column
        if not phone_col_indices:
            print("MASS SMS CSV DEBUGGING: Using first column as default phone column")
            phone_col_indices.append(0)
        
        print(f"MASS SMS CSV DEBUGGING: Using columns at indices {phone_col_indices} for phone numbers")
        print(f"MASS SMS CSV DEBUGGING: Treating first row as header: {header_row}")
        
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
                        print(f"MASS SMS CSV DEBUGGING: Row {row_idx}, Column {col_idx}: '{cell_value}' Valid: {is_valid}")
                        if is_valid:
                            normalized = normalize_phone_number(cell_value)
                            print(f"MASS SMS CSV DEBUGGING: Normalized: {normalized}")
                            phone_numbers.append(normalized)
                            valid_phones_found += 1
                            phone_found = True
                            break
                        else:
                            invalid_phones_found += 1
            
            if not phone_found and row_idx < start_row + 5:  # Only log first few rows to avoid flooding logs
                print(f"MASS SMS CSV DEBUGGING: No valid phone number found in row {row_idx}")
        
        print(f"MASS SMS CSV DEBUGGING: Found {valid_phones_found} valid and {invalid_phones_found} invalid phone numbers")
        
        # Remove duplicates while preserving order
        unique_phones = []
        seen = set()
        for phone in phone_numbers:
            if phone not in seen:
                seen.add(phone)
                unique_phones.append(phone)
        
        print(f"MASS SMS CSV DEBUGGING: Returning {len(unique_phones)} unique phone numbers")
        
        return {
            "status": "success", 
            "phone_numbers": unique_phones,
            "total": len(unique_phones)
        }
    
    except Exception as e:
        print(f"MASS SMS CSV DEBUGGING ERROR: {str(e)}")
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

@app.route('/mass_sms_upload', methods=['POST'])
def mass_sms_upload():
    """Handle CSV upload for mass SMS"""
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
        result = process_mass_sms_csv(file_content)
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Return the extracted phone numbers for preview
        return jsonify({
            "status": "success",
            "message": f"Successfully extracted {result['total']} phone numbers from CSV",
            "phone_numbers": result["phone_numbers"],
            "total": result["total"]
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500

@app.route('/send_mass_sms', methods=['POST'])
def send_mass_sms_endpoint():
    """Send mass SMS to phone numbers"""
    try:
        data = request.get_json()
        
        phone_numbers = data.get('phone_numbers', [])
        message = data.get('message', '')
        
        if not phone_numbers:
            return jsonify({"status": "error", "message": "No phone numbers provided"}), 400
        
        if not message or not message.strip():
            return jsonify({"status": "error", "message": "Message cannot be empty"}), 400
        
        # Send the mass SMS
        results = send_mass_sms(phone_numbers, message)
        
        if results["status"] == "error":
            return jsonify(results), 400
        
        return jsonify({
            "status": "success",
            "message": f"Mass SMS sent to {len(results['success'])} recipients",
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
        input[type="text"], input[type="url"], textarea, input[type="file"], input[type="number"], select {
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
        .phone-number-item {
            display: inline-block;
            margin: 2px 5px;
            padding: 3px 8px;
            background-color: #e9ecef;
            border-radius: 12px;
            font-size: 12px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 SMS Management Dashboard</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="openTab(event, 'tab-single')">Single Number</div>
            <div class="tab" onclick="openTab(event, 'tab-csv')">CSV Upload</div>
            <div class="tab" onclick="openTab(event, 'tab-mass-sms')">Mass SMS</div>
            <div class="tab" onclick="openTab(event, 'tab-survey')">Send Survey</div>
            <div class="tab" onclick="openTab(event, 'tab-manage')">Manage Data</div>
        </div>
        
        <!-- Single Number Tab -->
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
        
        <!-- CSV Upload Tab -->
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
                <div style="margin: 10px 0;">
                    <input type="checkbox" id="sendImmediately">
                    <label for="sendImmediately" style="display: inline; font-weight: normal; margin-left: 5px;">Send consent requests immediately after upload</label>
                </div>
                <button onclick="uploadCSV()">Upload CSV</button>
                
                <div id="previewArea" class="preview-area">
                    <div style="font-weight: bold; margin-bottom: 10px;">Phone Numbers Preview:</div>
                    <ul id="phonePreview" style="margin: 0; padding-left: 20px;"></ul>
                    <div id="previewControls" style="margin-top: 15px; display: none;">
                        <button onclick="sendConsentToPreview()">Send Consent Requests to These Numbers</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Mass SMS Tab -->
        <div id="tab-mass-sms" class="tab-content">
            <div class="section">
                <h2>📱 Mass SMS Service</h2>
                <p style="color: #666; margin-bottom: 20px;">
                    Send custom SMS messages to a list of phone numbers from a CSV file. 
                    <strong>Note:</strong> This service sends messages directly without requiring consent - use responsibly.
                </p>
                
                <!-- Step 1: Upload CSV -->
                <div style="margin-bottom: 30px; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #f8f9fa;">
                    <h3 style="margin-top: 0;">Step 1: Upload Phone Numbers</h3>
                    <div class="form-group">
                        <label for="massSmsFile">Select CSV file with phone numbers:</label>
                        <input type="file" id="massSmsFile" accept=".csv">
                    </div>
                    <button onclick="uploadMassSmsCSV()" style="background-color: #17a2b8;">📂 Upload & Preview Numbers</button>
                    
                    <div id="massSmsPreview" class="preview-area">
                        <div style="font-weight: bold; margin-bottom: 10px;">📋 Phone Numbers Preview (<span id="massSmsCount">0</span> numbers found):</div>
                        <div id="massSmsPhoneList" style="max-height: 200px; overflow-y: auto; margin: 10px 0; padding: 10px; border: 1px solid #ccc; border-radius: 3px; background-color: white;"></div>
                    </div>
                </div>
                
                <!-- Step 2: Compose Message -->
                <div style="margin-bottom: 30px; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #f8f9fa;">
                    <h3 style="margin-top: 0;">Step 2: Compose Your Message</h3>
                    <div class="form-group">
                        <label for="massSmsMessage">Message Text:</label>
                        <textarea id="massSmsMessage" rows="4" placeholder="Enter your message here..."></textarea>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
                            <span id="charCount" style="color: #666; font-size: 14px;">0 characters</span>
                            <span style="color: #666; font-size: 12px;">💡 SMS limit: 160 characters per message</span>
                        </div>
                    </div>
                    
                    <div style="margin-top: 15px; padding: 10px; background-color: white; border: 1px solid #ddd; border-radius: 5px;">
                        <strong>Message Preview:</strong>
                        <div id="messagePreview" style="margin-top: 5px; padding: 8px; background-color: #e9ecef; border-radius: 3px; font-family: monospace; min-height: 20px; white-space: pre-wrap;">Your message will appear here...</div>
                    </div>
                </div>
                
                <!-- Step 3: Send -->
                <div style="margin-bottom: 20px; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #fff3cd;">
                    <h3 style="margin-top: 0;">Step 3: Send Mass SMS</h3>
                    <div style="margin-bottom: 15px;">
                        <strong>Ready to send:</strong>
                        <div id="sendSummary" style="margin-top: 5px; color: #666;">Upload a CSV file and write a message to get started.</div>
                    </div>
                    
                    <div style="text-align: center;">
                        <button id="sendMassSmsBtn" onclick="sendMassSMS()" disabled style="background-color: #28a745; font-size: 18px; padding: 15px 30px; opacity: 0.6;">🚀 Send Mass SMS</button>
                    </div>
                </div>
                
                <div id="massSmsResults" style="display: none; margin-top: 20px; padding: 15px; border-radius: 5px;">
                    <h3>📊 Send Results</h3>
                    <div id="massSmsResultsContent"></div>
                </div>
            </div>
        </div>
        
        <!-- Send Survey Tab -->
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
        
        <!-- Manage Data Tab -->
        <div id="tab-manage" class="tab-content">
            <div class="section">
                <h2>Manage Participants</h2>
                <div style="margin-bottom: 15px;">
                    <button onclick="viewParticipants()">View All Participants</button>
                    <button onclick="exportData()">Export Data to CSV</button>
                </div>
                <div id="participantsTable" style="margin-top: 20px; display: none;">
                    <table>
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th>Phone Number</th>
                                <th>Consent Status</th>
                                <th>Email</th>
                                <th>Survey Sent</th>
                                <th>Additional Data</th>
                            </tr>
                        </thead>
                        <tbody id="participantsBody"></tbody>
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
        let massSmsPhoneNumbers = [];

        function openTab(evt, tabName) {
            const tabContents = document.getElementsByClassName("tab-content");
            for (let i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove("active");
            }
            
            const tabs = document.getElementsByClassName("tab");
            for (let i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove("active");
            }
            
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
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
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

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('send_immediately', sendImmediately);

            try {
                const response = await fetch(`${API_BASE}/upload_csv`, {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                
                if (response.ok) {
                    if (sendImmediately) {
                        showStatus(`Successfully sent consent requests to ${result.successful_sends} out of ${result.total_participants} phone numbers`, true);
                    } else {
                        extractedPhoneNumbers = result.participants_data ? result.participants_data.map(p => p.phone_number) : [];
                        
                        const previewArea = document.getElementById('previewArea');
                        const phonePreview = document.getElementById('phonePreview');
                        const previewControls = document.getElementById('previewControls');
                        
                        phonePreview.innerHTML = '';
                        
                        if (extractedPhoneNumbers.length > 0) {
                            extractedPhoneNumbers.forEach(phone => {
                                const li = document.createElement('li');
                                li.textContent = phone;
                                phonePreview.appendChild(li);
                            });
                            previewControls.style.display = 'block';
                        }
                        
                        previewArea.style.display = 'block';
                        showStatus(`Successfully extracted ${extractedPhoneNumbers.length} phone numbers from CSV`, true);
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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone_numbers: extractedPhoneNumbers })
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

        // Mass SMS functions
        async function uploadMassSmsCSV() {
            const fileInput = document.getElementById('massSmsFile');
            
            if (!fileInput.files || fileInput.files.length === 0) {
                showStatus('Please select a CSV file', false);
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            try {
                const response = await fetch(`${API_BASE}/mass_sms_upload`, {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                
                if (response.ok && result.status === 'success') {
    showStatus(`Mass SMS sent successfully to ${result.successful_sends} recipients!`, true);
    
    // Clear form
    document.getElementById('massSmsMessage').value = '';
    document.getElementById('massSmsFile').value = '';
    massSmsPhoneNumbers = [];
    document.getElementById('massSmsPreview').style.display = 'none';
    updateSendSummary();
} else {
    // Make sure we're showing the actual message, not the word "status"
    const errorMessage = result.message || result.error || 'Error sending mass SMS';
    showStatus(errorMessage, false);
}

        function displayMassSmsPreview(phoneNumbers) {
            const previewDiv = document.getElementById('massSmsPreview');
            const countSpan = document.getElementById('massSmsCount');
            const phoneList = document.getElementById('massSmsPhoneList');
            
            countSpan.textContent = phoneNumbers.length;
            phoneList.innerHTML = '';
            
            if (phoneNumbers.length > 0) {
                phoneNumbers.forEach(phone => {
                    const span = document.createElement('span');
                    span.className = 'phone-number-item';
                    span.textContent = phone;
                    phoneList.appendChild(span);
                });
                previewDiv.style.display = 'block';
            } else {
                previewDiv.style.display = 'none';
            }
        }

        function updateSendSummary() {
            const sendSummary = document.getElementById('sendSummary');
            const sendBtn = document.getElementById('sendMassSmsBtn');
            const message = document.getElementById('massSmsMessage') ? document.getElementById('massSmsMessage').value : '';
            
            if (massSmsPhoneNumbers.length > 0 && message.trim()) {
                const messageCount = message.length > 160 ? Math.ceil(message.length / 160) : 1;
                const totalSms = massSmsPhoneNumbers.length * messageCount;
                
                sendSummary.innerHTML = `<strong>${massSmsPhoneNumbers.length}</strong> recipients × <strong>${messageCount}</strong> SMS = <strong>${totalSms}</strong> total messages`;
                
                sendBtn.disabled = false;
                sendBtn.style.opacity = '1';
            } else {
                sendSummary.textContent = 'Upload a CSV file and write a message to get started.';
                sendBtn.disabled = true;
                sendBtn.style.opacity = '0.6';
            }
        }

        async function sendMassSMS() {
            const message = document.getElementById('massSmsMessage').value.trim();
            
            if (massSmsPhoneNumbers.length === 0) {
                showStatus('Please upload a CSV file with phone numbers first', false);
                return;
            }
            
            if (!message) {
                showStatus('Please enter a message to send', false);
                return;
            }
            
            const confirmed = confirm(`Send this message to ${massSmsPhoneNumbers.length} recipients?`);
            if (!confirmed) return;
            
            const sendBtn = document.getElementById('sendMassSmsBtn');
            sendBtn.disabled = true;
            sendBtn.textContent = '📤 Sending...';
            
            try {
                const response = await fetch(`${API_BASE}/send_mass_sms`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        phone_numbers: massSmsPhoneNumbers,
                        message: message
                    })
                });
                
                const result = await response.json();
                
                if (response.ok && result.status === 'success') {
                    showStatus(`Mass SMS sent successfully to ${result.successful_sends} recipients!`, true);
                    
                    // Clear form
                    document.getElementById('massSmsMessage').value = '';
                    document.getElementById('massSmsFile').value = '';
                    massSmsPhoneNumbers = [];
                    document.getElementById('massSmsPreview').style.display = 'none';
                } else {
                    showStatus(result.message || 'Error sending mass SMS', false);
                }
            } catch (error) {
                showStatus('Error sending mass SMS: ' + error.message, false);
            } finally {
                sendBtn.disabled = false;
                sendBtn.textContent = '🚀 Send Mass SMS';
                updateSendSummary();
            }
        }

        // Initialize character counter for mass SMS
        document.addEventListener('DOMContentLoaded', function() {
            const messageTextarea = document.getElementById('massSmsMessage');
            if (messageTextarea) {
                messageTextarea.addEventListener('input', function() {
                    const charCount = document.getElementById('charCount');
                    const messagePreview = document.getElementById('messagePreview');
                    const message = this.value;
                    
                    if (charCount) charCount.textContent = `${message.length} characters`;
                    if (messagePreview) messagePreview.textContent = message || 'Your message will appear here...';
                    
                    updateSendSummary();
                });
            }
        });

        async function sendSurvey() {
            const surveyUrl = document.getElementById('surveyUrl').value;
            const customMessage = document.getElementById('customMessage').value;
            
            if (!surveyUrl) {
                showStatus('Please enter a survey URL', false);
                return;
            }

            try {
                const body = `survey_url=${encodeURIComponent(surveyUrl)}`;
                const fullBody = customMessage ? `${body}&custom_message=${encodeURIComponent(customMessage)}` : body;
                
                const response = await fetch(`${API_BASE}/send_survey`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
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
            const modal = document.createElement('div');
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;justify-content:center;align-items:center;z-index:1000';
            
            const content = document.createElement('div');
            content.style.cssText = 'background:white;padding:20px;border-radius:5px;width:80%;max-width:600px;max-height:80%;overflow-y:auto';
            
            content.innerHTML = `
                <h3>Additional Data for ${participant.phone_number}</h3>
                <button onclick="document.body.removeChild(this.closest('div[style*=\"position:fixed\"]'))" style="float:right;">Close</button>
                <table style="width:100%;border-collapse:collapse;margin-top:10px;">
                    <tr><th style="text-align:left;padding:8px;border-bottom:1px solid #ddd;">Field</th><th style="text-align:left;padding:8px;border-bottom:1px solid #ddd;">Value</th></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Call Time</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.calltime || 'N/A'}</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Vote Intent</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.last_fed_vote_intent || 'N/A'}</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Gender</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.gender || 'N/A'}</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Age</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.age || 'N/A'}</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Education</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.education || 'N/A'}</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Phone Type</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.phone_type || 'N/A'}</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Region</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.region || 'N/A'}</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #ddd;">Notes</td><td style="padding:8px;border-bottom:1px solid #ddd;">${participant.notes || 'N/A'}</td></tr>
                </table>
            `;
            
            modal.appendChild(content);
            document.body.appendChild(modal);
            
            modal.addEventListener('click', (e) => {
                if (e.target === modal) document.body.removeChild(modal);
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
                
                if (document.getElementById('participantsTable').style.display !== 'none') {
                    viewParticipants();
                }
            } catch (error) {
                showStatus('Error resetting survey status: ' + error.message, false);
            }
        }

        function exportData() {
            showStatus('Starting data export...', true);
            
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            document.body.appendChild(iframe);
            
            iframe.src = `${API_BASE}/export_data`;
            
            setTimeout(() => {
                showStatus('Download started. Check your downloads folder.', true);
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
