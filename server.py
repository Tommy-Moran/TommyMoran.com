from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os
import time

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure CORS to allow requests from your frontend
CORS(app, resources={
    r"/chat": {
        "origins": ["http://localhost:8000", "http://127.0.0.1:8000"],
        "methods": ["POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response

    try:
        data = request.json
        user_message = data.get('message', '')

        # Create a thread
        thread = client.beta.threads.create()

        # Add the user's message to the thread
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )

        # Run the assistant on the thread
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_TuRXN1c893HGDyQvzO83W3YT"
        )

        # Wait for the run to complete
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            elif run_status.status == 'failed':
                raise Exception("Assistant run failed")
            time.sleep(1)  # Wait for 1 second before checking again

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        
        # Get the last assistant message
        for message in messages.data:
            if message.role == "assistant":
                assistant_message = message.content[0].text.value
                # Remove any reference links or citations
                assistant_message = assistant_message.split('【')[0].strip()
                # Ensure the message ends with proper punctuation
                if not assistant_message.endswith(('.', '!', '?')):
                    assistant_message = assistant_message.rstrip() + '.'
                return jsonify({
                    'response': assistant_message
                })
        
        # If no assistant message found
        return jsonify({
            'error': 'No response from assistant'
        }), 500
        
    except Exception as e:
        print(f"Error: {str(e)}")  # Add server-side logging
        return jsonify({
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True) 