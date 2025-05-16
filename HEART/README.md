# HEART (Hobart Echo Appropriateness Review Tool)

HEART is a clinical guidance web app for Royal Hobart Hospital that reviews requests for echocardiograms to assess appropriateness, urgency, and whether scans should be inpatient or outpatient, using a set of validated criteria and an OpenAI-powered assistant.

## Overview

This application helps clinicians determine:
- Whether an echocardiogram is appropriate for the clinical situation
- If appropriate, whether it should be performed as an inpatient or outpatient
- The relative urgency of the study
- Recommendations for other investigations or consultations if applicable

All user inputs and AI responses are logged to an Excel Online sheet for auditing.

## Features

- Responsive web design that works on both mobile and desktop
- Multi-step form to collect patient URN and clinical details
- OpenAI integration for intelligent assessment of echo appropriateness
- Secure logging of all assessments to Excel Online
- Clipboard functionality to easily copy clinical information
- Clear guidance for next steps based on the assessment outcome

## Technical Stack

- **Framework**: Next.js with TypeScript
- **Styling**: Tailwind CSS
- **AI**: OpenAI Assistant API
- **Data Storage**: Microsoft Excel Online via Graph API
- **Hosting**: To be determined (not included in this initial setup)

## Setup Instructions

For detailed setup instructions including secure API key configuration, please see [SETUP.md](./SETUP.md).

Quick start:

1. Create a `.env.local` file with your API keys (see SETUP.md)
2. Install dependencies:
   ```
   npm install
   ```
3. Run the development server:
   ```
   npm run dev
   ```

## Application Flow

1. **Landing Page**: Displays app title, disclaimer, and start button
2. **URN Entry**: Collects the patient's Royal Hobart Hospital URN
3. **Clinical Context**: Collects relevant clinical information and specific question
4. **Assessment**: AI analyzes the clinical information and provides recommendations
5. **Results**: Displays assessment outcome and provides next steps based on the recommendation

## Data Security

- URN is stored only for audit purposes and is not sent to the AI
- No patient identifiable information should be entered in the clinical context
- All data is encrypted in transit (HTTPS)
- Excel audit logs are accessible only to authorized users
- API keys are stored securely as environment variables and never exposed client-side

## Contact

For more information, contact Dr. Tommy Moran.

## License

This project is proprietary and owned by Royal Hobart Hospital. 