from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os
import time
import httpx
import logging
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Determine allowed origins based on environment
_prod_origins = [
    "https://tommymoran.com",
    "https://tommymoran-com-chatbot.onrender.com",
]
_dev_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:8082",
    "http://127.0.0.1:8082",
]
ALLOWED_ORIGINS = _prod_origins + (_dev_origins if os.getenv('FLASK_ENV') == 'development' else [])

# Enable CORS
CORS(app, resources={
    r"/chat": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": False
    }
})

# Security headers applied to every response
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response

# Simple in-memory rate limiting (per IP, 10 requests/minute)
_rate_limit_store = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 10
MAX_MESSAGE_LENGTH = 1000

def is_rate_limited(ip):
    now = time.time()
    window_start = now - 60
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if t > window_start]
    if len(_rate_limit_store[ip]) >= MAX_REQUESTS_PER_MINUTE:
        return True
    _rate_limit_store[ip].append(now)
    return False

# Initialize OpenAI client with custom HTTP client
try:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
    if not assistant_id:
        logger.error("OPENAI_ASSISTANT_ID environment variable is not set")
        raise ValueError("OPENAI_ASSISTANT_ID environment variable is not set")

    # Create an event hook to add the v2 header
    def add_v2_header(request):
        request.headers["OpenAI-Beta"] = "assistants=v2"
        return request

    # Create HTTP client with event hook and increased timeout
    http_client = httpx.Client(
        timeout=60.0,
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
        response = jsonify({'status': 'ok'})
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response

    # Rate limiting
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
    client_ip = client_ip.split(',')[0].strip()
    if is_rate_limited(client_ip):
        return jsonify({'error': 'Too many requests. Please wait a moment and try again.'}), 429

    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Invalid request body.'}), 400

        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({'error': 'Message is required.'}), 400
        if len(user_message) > MAX_MESSAGE_LENGTH:
            return jsonify({'error': f'Message too long. Maximum {MAX_MESSAGE_LENGTH} characters.'}), 400

        logger.info(f"Received message of length {len(user_message)}")

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
            assistant_id=assistant_id
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
                time.sleep(1)

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
                    if hasattr(message.content[0], 'text') and hasattr(message.content[0].text, 'value'):
                        assistant_message = message.content[0].text.value
                    elif isinstance(message.content[0], dict) and 'text' in message.content[0]:
                        assistant_message = message.content[0]['text']
                    elif hasattr(message.content[0], 'text') and isinstance(message.content[0].text, dict):
                        assistant_message = message.content[0].text.get('value', '')
                    else:
                        logger.warning(f"Unexpected message content format")
                        continue

                    # Remove any reference links or citations
                    assistant_message = assistant_message.split('【')[0].strip()
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

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 8081))
        logger.info(f"Starting server on port {port}")
        logger.info(f"OpenAI API Key present: {bool(os.getenv('OPENAI_API_KEY'))}")
        logger.info(f"Assistant ID configured: {bool(os.getenv('OPENAI_ASSISTANT_ID'))}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise
