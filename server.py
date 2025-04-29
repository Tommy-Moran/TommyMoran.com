from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os
import time
import httpx
import logging

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
    }
})

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

@app.route('/debug')
def debug():
    logger.info("Debug endpoint accessed")
    return jsonify({
        "status": "ok",
        "openai_api_key_set": bool(os.getenv('OPENAI_API_KEY')),
        "port": os.getenv('PORT'),
        "python_version": os.getenv('PYTHON_VERSION')
    })

if __name__ == '__main__':
    try:
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