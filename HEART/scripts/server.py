from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import random
import datetime
import sqlite3
import json

app = Flask(__name__)
# Configure CORS to allow requests from TommyMoran.com
CORS(app, origins=["https://tommymoran.com", "http://localhost:3000"])

# Database setup
def init_db():
    conn = sqlite3.connect('heart_audit.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT UNIQUE,
        clinical_context TEXT,
        clinical_question TEXT,
        ai_response TEXT,
        timestamp TEXT,
        created_at TEXT
    )
    ''')
    conn.commit()
    conn.close()

# Initialize database
init_db()

def generate_case_id():
    """Generate a unique case ID starting with H followed by 6 random digits"""
    return f"H{random.randint(100000, 999999)}"

@app.route('/api/log-assessment', methods=['POST'])
def log_assessment():
    data = request.json
    
    # Extract data from request
    clinical_context = data.get('clinicalContext', '')
    clinical_question = data.get('clinicalQuestion', '')
    ai_response = json.dumps(data.get('aiResponse', {}))
    timestamp = data.get('timestamp', datetime.datetime.now().isoformat())
    
    # Generate a unique case ID
    case_id = generate_case_id()
    
    # Ensure case ID is unique by checking the database
    conn = sqlite3.connect('heart_audit.db')
    cursor = conn.cursor()
    
    is_unique = False
    while not is_unique:
        cursor.execute("SELECT case_id FROM audit_logs WHERE case_id = ?", (case_id,))
        if cursor.fetchone() is None:
            is_unique = True
        else:
            case_id = generate_case_id()
    
    # Store in database
    created_at = datetime.datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO audit_logs (case_id, clinical_context, clinical_question, ai_response, timestamp, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (case_id, clinical_context, clinical_question, ai_response, timestamp, created_at)
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "caseId": case_id
    })

@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    # Simple password protection (in real app, use proper auth)
    provided_password = request.headers.get('X-Audit-Password')
    if provided_password != os.environ.get('AUDIT_PASSWORD', 'heart-audit-password'):
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = sqlite3.connect('heart_audit.db')
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    # Convert to list of dicts
    logs = []
    for row in rows:
        log = {
            'id': row['id'],
            'caseId': row['case_id'],
            'clinicalContext': row['clinical_context'],
            'clinicalQuestion': row['clinical_question'],
            'aiResponse': json.loads(row['ai_response']),
            'timestamp': row['timestamp'],
            'createdAt': row['created_at']
        }
        logs.append(log)
    
    conn.close()
    
    return jsonify(logs)

@app.route('/api/audit-logs/csv', methods=['GET'])
def get_audit_logs_csv():
    # Simple password protection (in real app, use proper auth)
    provided_password = request.headers.get('X-Audit-Password')
    if provided_password != os.environ.get('AUDIT_PASSWORD', 'heart-audit-password'):
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = sqlite3.connect('heart_audit.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    # Create CSV content
    csv_content = "ID,Case ID,Clinical Context,Clinical Question,Recommendation,Rationale,Created At\n"
    
    for row in rows:
        ai_response = json.loads(row['ai_response'])
        recommendation = ai_response.get('recommendation', '').replace('"', '""')
        rationale = ai_response.get('rationale', '').replace('"', '""')
        
        csv_line = f'"{row["id"]}","{row["case_id"]}","{row["clinical_context"].replace('"', '""')}","{row["clinical_question"].replace('"', '""')}","{recommendation}","{rationale}","{row["created_at"]}"\n'
        csv_content += csv_line
    
    conn.close()
    
    response = app.response_class(
        response=csv_content,
        status=200,
        mimetype='text/csv'
    )
    response.headers["Content-Disposition"] = "attachment; filename=heart_audit_logs.csv"
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port) 