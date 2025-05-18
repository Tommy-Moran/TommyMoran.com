from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os
import time
import httpx
import logging
import uuid
import json
from datetime import datetime
import csv
from io import StringIO
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes with proper configuration
CORS(app, resources={
    r"/chat": {
        "origins": [
            "https://tommymoran.com",
            "https://tommymoran-com-chatbot.onrender.com",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:8082",
            "http://127.0.0.1:8082"
        ],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    },
    r"/HEART/assess": {
        "origins": [
            "https://tommymoran.com",
            "https://tommymoran-com-chatbot.onrender.com",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:8082",
            "http://127.0.0.1:8082"
        ],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

# Setup database file for HEART case tracking
HEART_DB_FILE = "heart_cases.json"

# Initialize the database if it doesn't exist
def initialize_heart_db():
    if not os.path.exists(HEART_DB_FILE):
        with open(HEART_DB_FILE, 'w') as f:
            json.dump([], f)
        logger.info(f"Initialized empty HEART database at {HEART_DB_FILE}")

# Save a HEART case to the database
def save_heart_case(case_id, clinical_context, clinical_question, ai_response):
    try:
        # Load existing database
        if os.path.exists(HEART_DB_FILE):
            with open(HEART_DB_FILE, 'r') as f:
                cases = json.load(f)
        else:
            cases = []
        
        # Add new case
        cases.append({
            'case_id': case_id,
            'timestamp': datetime.now().isoformat(),
            'clinical_context': clinical_context,
            'clinical_question': clinical_question,
            'ai_response': ai_response
        })
        
        # Save updated database
        with open(HEART_DB_FILE, 'w') as f:
            json.dump(cases, f, indent=2)
        
        logger.info(f"Successfully saved HEART case {case_id} to database")
        return True
    except Exception as e:
        logger.error(f"Error saving HEART case to database: {str(e)}")
        return False

# Initialize OpenAI client with custom HTTP client
try:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    # Create an event hook to add the v2 header
    def add_v2_header(request):
        request.headers["OpenAI-Beta"] = "assistants=v2"
        return request
    
    # Create HTTP client with event hook and increased timeout
    http_client = httpx.Client(
        timeout=60.0,  # Increased timeout to 60 seconds
        event_hooks={
            'request': [add_v2_header]
        }
    )
    
    client = OpenAI(
        api_key=api_key,
        http_client=http_client,
        max_retries=3
    )
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    raise

@app.route('/')
def index():
    logger.info("Root route accessed")
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    logger.info("Chat endpoint accessed")
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'status': 'ok'})
        # Get the Origin header from the request
        origin = request.headers.get('Origin')
        # Check if the origin is in our allowed origins
        allowed_origins = [
            "https://tommymoran.com",
            "https://tommymoran-com-chatbot.onrender.com",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:8082",
            "http://127.0.0.1:8082"
        ]
        if origin in allowed_origins:
            response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response

    try:
        data = request.json
        user_message = data.get('message', '')
        logger.info(f"Received message: {user_message}")

        # Create a thread
        thread = client.beta.threads.create()
        logger.info(f"Created thread: {thread.id}")

        # Add the user's message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )
        logger.info(f"Added message to thread: {message.id}")

        # Run the assistant on the thread
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_TuRXN1c893HGDyQvzO83W3YT"
        )
        logger.info(f"Created run: {run.id}")

        # Wait for the run to complete with a maximum timeout
        max_attempts = 30  # 30 seconds maximum
        attempts = 0
        
        while attempts < max_attempts:
            try:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                
                if run_status.status == 'completed':
                    break
                elif run_status.status == 'failed':
                    logger.error(f"Run failed: {run_status.last_error}")
                    return jsonify({
                        'error': f"Assistant run failed: {run_status.last_error}"
                    }), 500
                elif run_status.status == 'expired':
                    logger.error("Run expired")
                    return jsonify({
                        'error': "Assistant run expired. Please try again."
                    }), 500
                
                attempts += 1
                time.sleep(1)  # Wait for 1 second before checking again
                
            except Exception as e:
                logger.error(f"Error checking run status: {str(e)}")
                return jsonify({
                    'error': "Error communicating with OpenAI. Please try again."
                }), 500

        if attempts >= max_attempts:
            logger.error("Run timed out")
            return jsonify({
                'error': "Request timed out. Please try again."
            }), 500

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        logger.info("Retrieved messages from thread")
        
        # Get the last assistant message
        for message in messages.data:
            if message.role == "assistant":
                try:
                    # Handle different possible message content structures
                    if hasattr(message.content[0], 'text') and hasattr(message.content[0].text, 'value'):
                        assistant_message = message.content[0].text.value
                    elif isinstance(message.content[0], dict) and 'text' in message.content[0]:
                        assistant_message = message.content[0]['text']
                    elif hasattr(message.content[0], 'text') and isinstance(message.content[0].text, dict):
                        assistant_message = message.content[0].text.get('value', '')
                    else:
                        logger.warning(f"Unexpected message content format: {message.content}")
                        continue
                    
                    # Remove any reference links or citations
                    assistant_message = re.sub(r'【.*?】', '', assistant_message).strip()
                    # Ensure the message ends with proper punctuation
                    if not assistant_message.endswith(('.', '!', '?')):
                        assistant_message = assistant_message.rstrip() + '.'
                    logger.info("Successfully processed assistant response")
                    return jsonify({
                        'response': assistant_message
                    })
                except Exception as e:
                    logger.error(f"Error processing message content: {str(e)}")
                    continue
        
        # If no assistant message found
        logger.warning("No assistant message found in thread")
        return jsonify({
            'error': 'No response from assistant'
        }), 500
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/HEART/assess', methods=['POST', 'OPTIONS'])
def heart_assess():
    logger.info("HEART assessment endpoint accessed")
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'status': 'ok'})
        origin = request.headers.get('Origin')
        allowed_origins = [
            "https://tommymoran.com",
            "https://tommymoran-com-chatbot.onrender.com",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:8082",
            "http://127.0.0.1:8082"
        ]
        if origin in allowed_origins:
            response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response

    try:
        data = request.json
        clinical_context = data.get('clinical_context', '')
        clinical_question = data.get('clinical_question', '')
        
        # Generate a unique 7-digit case ID
        case_id = str(uuid.uuid4().int)[:7]
        logger.info(f"HEART assessment request: Case ID {case_id}")
        
        # Format the message for the HEART assistant
        user_message = (
            f"Clinical Context: {clinical_context}\n\n"
            f"Clinical Question: {clinical_question}\n\n"
            "Please provide your response in the following sections:\n"
            "Recommendation: State only if the scan is indicated, whether it should be inpatient or outpatient, and the recommended timeframe. Do not include clinical reasoning or details here.\n"
            "Rationale: Provide the clinical reasoning and details here.\n"
            "Next Steps: List any recommended actions or follow-up.\n"
            "Consider Consulting: List any teams or specialties that should be consulted, if relevant.\n"
        )

        # Create a thread
        thread = client.beta.threads.create()
        logger.info(f"Created thread for HEART: {thread.id}")

        # Add the user's message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )
        logger.info(f"Added message to HEART thread: {message.id}")

        # Run the HEART assistant on the thread
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_W3VfOMmKvt07w6WIR6yGpI9x"
        )
        logger.info(f"Created HEART run: {run.id}")

        # Wait for the run to complete with a maximum timeout
        max_attempts = 60  # 60 seconds maximum (may need longer for complex cases)
        attempts = 0
        
        while attempts < max_attempts:
            try:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                
                if run_status.status == 'completed':
                    break
                elif run_status.status == 'failed':
                    logger.error(f"HEART run failed: {run_status.last_error}")
                    return jsonify({
                        'error': f"HEART assessment failed: {run_status.last_error}"
                    }), 500
                elif run_status.status == 'expired':
                    logger.error("HEART run expired")
                    return jsonify({
                        'error': "HEART assessment expired. Please try again."
                    }), 500
                
                attempts += 1
                time.sleep(1)  # Wait for 1 second before checking again
                
            except Exception as e:
                logger.error(f"Error checking HEART run status: {str(e)}")
                return jsonify({
                    'error': "Error communicating with OpenAI. Please try again."
                }), 500

        if attempts >= max_attempts:
            logger.error("HEART run timed out")
            return jsonify({
                'error': "HEART assessment timed out. Please try again."
            }), 500

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        logger.info("Retrieved messages from HEART thread")
        
        # Get the last assistant message
        for message in messages.data:
            if message.role == "assistant":
                try:
                    # Handle different possible message content structures
                    if hasattr(message.content[0], 'text') and hasattr(message.content[0].text, 'value'):
                        assistant_message = message.content[0].text.value
                    elif isinstance(message.content[0], dict) and 'text' in message.content[0]:
                        assistant_message = message.content[0]['text']
                    elif hasattr(message.content[0], 'text') and isinstance(message.content[0].text, dict):
                        assistant_message = message.content[0].text.get('value', '')
                    else:
                        logger.warning(f"Unexpected HEART message content format: {message.content}")
                        continue
                    
                    # Save the HEART case to the database
                    save_heart_case(case_id, clinical_context, clinical_question, assistant_message)
                    
                    # Parse the sections from the response
                    try:
                        sections = {}
                        current_section = None
                        lines = assistant_message.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line.endswith(':'):
                                current_section = line[:-1]  # Remove the colon
                                sections[current_section] = ''
                            elif current_section and line:
                                if sections[current_section]:
                                    sections[current_section] += '\n' + line
                                else:
                                    sections[current_section] = line
                    except Exception as e:
                        logger.error(f"Error parsing HEART response sections: {str(e)}")
                        sections = {
                            "Recommendation": assistant_message,
                            "Rationale": "",
                            "Next Steps": "",
                            "Consult Other Teams": ""
                        }
                        
                    # Replace timeframe with category in Recommendation section
                    if "Recommendation" in sections and isinstance(sections["Recommendation"], str):
                        sections["Recommendation"] = standardize_recommendation(sections["Recommendation"])
                        # Also update the assistant_message if possible
                        rec_start = assistant_message.find('Recommendation:')
                        if rec_start != -1:
                            next_section_match = re.search(r'\n\s*(Rationale|Next Steps|Consider Consulting|Consult Other Teams):', assistant_message[rec_start+14:])
                            if next_section_match:
                                rec_end = rec_start + 14 + next_section_match.start()
                                assistant_message = assistant_message[:rec_start+14] + '\n' + sections["Recommendation"] + assistant_message[rec_end:]
                            else:
                                assistant_message = assistant_message[:rec_start+14] + '\n' + sections["Recommendation"]
                    
                    # Remove any reference links or citations in the format '【...】' or '[...†...]'
                    assistant_message = remove_references(assistant_message)
                    for key in sections:
                        if isinstance(sections[key], str):
                            sections[key] = remove_references(sections[key])
                    
                    logger.info("Successfully processed HEART assistant response")
                    return jsonify({
                        'case_id': case_id,
                        'response': assistant_message,
                        'sections': sections
                    })
                except Exception as e:
                    logger.error(f"Error processing HEART message content: {str(e)}")
                    continue
        
        # If no assistant message found
        logger.warning("No HEART assistant message found in thread")
        return jsonify({
            'error': 'No response from HEART assistant'
        }), 500
        
    except Exception as e:
        logger.error(f"Error in HEART assessment endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/HEART/help', methods=['POST'])
def heart_help():
    try:
        data = request.json
        name = data.get('name', 'Unknown')
        email = data.get('email', 'Unknown')
        message = data.get('message', 'No message provided')
        
        # Here you would typically send an email
        # For now, we'll just log it
        logger.info(f"HEART help request received from {name} ({email}): {message}")
        
        # In a production environment, you would integrate with an email service
        
        return jsonify({
            'status': 'success',
            'message': 'Your help request has been received. We will respond to your email shortly.'
        })
    except Exception as e:
        logger.error(f"Error in HEART help endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/HEART/export-csv', methods=['GET'])
def export_heart_csv():
    try:
        if not os.path.exists(HEART_DB_FILE):
            return jsonify({'error': 'No data available'}), 404
        with open(HEART_DB_FILE, 'r') as f:
            cases = json.load(f)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['case_id', 'timestamp', 'clinical_context', 'clinical_question', 'ai_response'])
        for case in cases:
            writer.writerow([
                case.get('case_id', ''),
                case.get('timestamp', ''),
                case.get('clinical_context', ''),
                case.get('clinical_question', ''),
                case.get('ai_response', '')
            ])
        response = app.response_class(
            response=output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=heart_cases.csv'}
        )
        return response
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/HEART')
def heart_redirect():
    # Redirect /HEART to /HEART/
    return redirect('/HEART/')

@app.route('/HEART/<path:path>')
def heart_static(path):
    return send_from_directory('HEART', path)

@app.route('/HEART/')
def heart_index():
    return send_from_directory('HEART', 'index.html')

@app.route('/debug')
def debug():
    logger.info("Debug endpoint accessed")
    return jsonify({
        "status": "ok",
        "openai_api_key_set": bool(os.getenv('OPENAI_API_KEY')),
        "port": os.getenv('PORT'),
        "python_version": os.getenv('PYTHON_VERSION')
    })

# Add the remove_references function and update all relevant calls in /HEART/assess
def remove_references(text):
    text = re.sub(r'【.*?】', '', text)
    text = re.sub(r'\[.*?†.*?\]', '', text)
    return text.strip()

# Add after remove_references function
def replace_timeframe_with_category(text):
    import re
    # Patterns and their corresponding categories
    patterns = [
        (r"(immediate|urgent)", "Category 1 echocardiogram is indicated"),
        (r"(within|in|up to)\s*(\d+)[-\s]?(\d+)?\s*hours?", None),  # Range handled below
        (r"(within|in|up to)\s*24\s*hours?", "Category 2 echocardiogram is indicated"),
        (r"(within|in|up to)\s*36\s*hours?", "Category 3 echocardiogram is indicated"),
        (r">\s*48\s*hours?|within\s*a\s*few\s*days?", "Category 4 echocardiogram is indicated"),
        (r">\s*1\s*week|within\s*a\s*few\s*weeks|outpatient", "Category 5 echocardiogram is indicated"),
    ]
    # Handle ranges like "within 12-24 hours"
    def range_replacer(match):
        lower = int(match.group(2))
        upper = int(match.group(3)) if match.group(3) else lower
        if upper <= 1:
            return "Category 1 echocardiogram is indicated"
        elif upper <= 24:
            return "Category 2 echocardiogram is indicated"
        elif upper <= 36:
            return "Category 3 echocardiogram is indicated"
        elif upper <= 168:  # 7 days * 24 hours
            return "Category 4 echocardiogram is indicated"
        else:
            return "Category 5 echocardiogram is indicated"
    # Replace ranges first
    text = re.sub(r"(within|in|up to)\s*(\d+)[-\s]?(\d+)?\s*hours?", range_replacer, text, flags=re.IGNORECASE)
    # Replace other patterns
    for pattern, category in patterns:
        if category:
            text = re.sub(pattern, category, text, flags=re.IGNORECASE)
    return text

def standardize_recommendation(original_text):
    import re
    text_lower = original_text.lower()
    # If inpatient, always replace timeframe with category and standardize
    if "inpatient" in text_lower:
        # Map timeframe to category
        category = None
        # Match ranges like 'within 24-72 hours', 'within 24–72 hours', etc.
        match = re.search(r"(within|in|up to)\s*(\d+)[-–—]?(\d+)?\s*hours?", original_text, re.IGNORECASE)
        if match:
            upper = int(match.group(3)) if match.group(3) else int(match.group(2))
            if upper <= 1:
                category = "Category 1"
            elif upper <= 24:
                category = "Category 2"
            elif upper <= 36:
                category = "Category 3"
            elif upper <= 168:
                category = "Category 4"
            else:
                category = "Category 5"
        # Fallback if no timeframe found
        if not category:
            category = "Category (unspecified)"
        return f"A {category} echocardiogram is recommended as an inpatient."
    # Otherwise, use the AI's original recommendation
    return original_text.strip()

if __name__ == '__main__':
    try:
        # Initialize HEART database
        initialize_heart_db()
        
        # Get port from environment variable or default to 8081
        port = int(os.environ.get('PORT', 8081))
        logger.info(f"Starting server on port {port}")
        
        # Verify OpenAI client initialization
        logger.info(f"OpenAI API Key present: {bool(os.getenv('OPENAI_API_KEY'))}")
        logger.info(f"Assistant ID configured: {bool('asst_TuRXN1c893HGDyQvzO83W3YT')}")
        
        # Run on all interfaces (0.0.0.0) to allow external connections
        # Debug mode off to prevent auto-reloading
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise 