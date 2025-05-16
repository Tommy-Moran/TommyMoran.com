# HEART App Audit Feature

This document provides an overview of the audit functionality added to the HEART (Hospital Echo Appropriateness Request Tool) application.

## Overview

The audit feature allows you to track and review all echocardiogram appropriateness assessments performed through the HEART app. This is useful for:

- Evaluating the effectiveness of the tool
- Tracking patterns in appropriate and inappropriate requests
- Quality improvement
- Research purposes
- Training and education

## Features

### 1. Automatic Logging

Every assessment is automatically logged to a secure database, including:
- Clinical context
- Clinical question
- AI response (recommendation, rationale, next steps, consult recommendations)
- Timestamp
- Unique case ID

### 2. Unique Case IDs

Each case is assigned a unique identifier:
- Format: H followed by 6 random digits (e.g., H123456)
- This ID is included when copying clinical information for inpatient scans
- The ID allows for tracking the case through the echo request process

### 3. Enhanced Copy Feature

For cases where an echocardiogram is indicated:
- The copy button includes clinical context, clinical question, recommendation, and case ID
- This helps with audit tracking when the information is pasted into the echo request form

### 4. Admin Panel

A password-protected admin panel is available at `/admin`:
- View all logged assessments
- Filter and search through records
- Export data as CSV for further analysis
- Review clinical details for each case

### 5. Data Security

- No patient identifiers are stored (as per the original design)
- Admin access is password protected
- The backend is hosted on Render with appropriate security measures

## Technical Implementation

- **Frontend**: React/Next.js with TypeScript
- **Backend**: Flask Python API on Render
- **Database**: SQLite (can be upgraded to Postgres for production)
- **Authentication**: Simple password protection for admin access

## Deployment

- Frontend is deployed to GitHub Pages
- Backend API is deployed to Render
- See `DEPLOYMENT.md` for detailed deployment instructions

## Accessing Audit Logs

1. Navigate to `/admin` in the HEART app
2. Enter the audit password
3. View or download logs as needed

## Future Enhancements

Potential future improvements:
- More sophisticated analytics dashboard
- User authentication for different access levels
- Integration with hospital electronic medical record systems
- Automated reporting