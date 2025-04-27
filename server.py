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
            "http://localhost:8000"
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
    
    # Create a custom HTTP client with the v2 header
    class CustomHTTPClient(httpx.Client):
        def _prepare_request(self, request):
            request.headers["OpenAI-Beta"] = "assistants=v2"
            return super()._prepare_request(request)
    
    http_client = CustomHTTPClient(timeout=30.0)
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
        response.headers.add('Access-Control-Allow-Origin', 'https://tommymoran.com')
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

        # Wait for the run to complete
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            elif run_status.status == 'failed':
                logger.error(f"Run failed: {run_status.last_error}")
                raise Exception(f"Assistant run failed: {run_status.last_error}")
            time.sleep(1)  # Wait for 1 second before checking again

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        logger.info("Retrieved messages from thread")
        
        # Get the last assistant message
        for message in messages.data:
            if message.role == "assistant":
                assistant_message = message.content[0].text.value
                # Remove any reference links or citations
                assistant_message = assistant_message.split('【')[0].strip()
                # Ensure the message ends with proper punctuation
                if not assistant_message.endswith(('.', '!', '?')):
                    assistant_message = assistant_message.rstrip() + '.'
                logger.info("Successfully processed assistant response")
                return jsonify({
                    'response': assistant_message
                })
        
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
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Run on all interfaces (0.0.0.0) to allow external connections
    app.run(host='0.0.0.0', port=port, debug=False) 