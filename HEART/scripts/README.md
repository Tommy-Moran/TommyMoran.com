# HEART Audit Backend

This is the backend service for the HEART (Hospital Echo Appropriateness Request Tool) application. It provides API endpoints for storing and retrieving audit logs of echo appropriateness assessments.

## Features

- Logs all clinical context, questions, and AI responses
- Generates unique case IDs for each assessment
- Provides password-protected access to audit logs
- Allows CSV export of all logs

## Setup

### Prerequisites

- Python 3.7+
- Flask
- SQLite

### Installation

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set environment variables:
   - `AUDIT_PASSWORD` - Password for accessing audit logs

### Deployment to Render

1. Fork or clone this repository
2. Connect your GitHub account to Render
3. Create a new Web Service
4. Select the repository
5. Configure:
   - Environment: Python
   - Build Command: `pip install -r scripts/requirements.txt`
   - Start Command: `cd scripts && gunicorn server:app`
   - Add environment variable: `AUDIT_PASSWORD` (set a secure password)

## API Endpoints

### POST /api/log-assessment

Records a new assessment in the audit log.

**Request Body:**
```json
{
  "clinicalContext": "Patient history and context...",
  "clinicalQuestion": "Clinical question about echo...",
  "aiResponse": {
    "recommendation": "Inpatient echocardiogram is indicated...",
    "rationale": "Rationale for recommendation...",
    "nextSteps": "Next steps...",
    "consultOtherTeams": "Consider consulting..."
  },
  "timestamp": "2023-05-15T12:34:56.789Z"
}
```

**Response:**
```json
{
  "success": true,
  "caseId": "H123456"
}
```

### GET /api/audit-logs

Returns all audit logs in JSON format.

**Headers:**
- `X-Audit-Password`: Your audit password

**Response:**
```json
[
  {
    "id": 1,
    "caseId": "H123456",
    "clinicalContext": "Patient history...",
    "clinicalQuestion": "Clinical question...",
    "aiResponse": {
      "recommendation": "Recommendation...",
      "rationale": "Rationale...",
      "nextSteps": "Next steps...",
      "consultOtherTeams": "Consider consulting..."
    },
    "timestamp": "2023-05-15T12:34:56.789Z",
    "createdAt": "2023-05-15T12:34:56.789Z"
  },
  ...
]
```

### GET /api/audit-logs/csv

Downloads all audit logs in CSV format.

**Headers:**
- `X-Audit-Password`: Your audit password

**Response:**
CSV file download 