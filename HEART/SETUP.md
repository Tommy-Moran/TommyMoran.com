# HEART Application Setup Guide

This guide will help you set up the HEART application, including securely configuring the API keys.

## Environment Variables Setup

The application requires certain environment variables to function properly. These should be kept secure and never committed to version control.

### 1. Creating your .env.local file

Create a file named `.env.local` in the root directory of the project with the following content:

```
# OpenAI API Key - Keep this secure!
OPENAI_API_KEY=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

# OpenAI Assistant ID
OPENAI_ASSISTANT_ID=asst_qCeKG8yoFLKfbwQANHV28xNX

# Microsoft Graph API (when ready to implement Excel integration)
# MICROSOFT_GRAPH_CLIENT_ID=your_microsoft_app_id_here
# MICROSOFT_GRAPH_CLIENT_SECRET=your_microsoft_app_secret_here
# MICROSOFT_GRAPH_TENANT_ID=your_tenant_id_here

# Excel File ID
# EXCEL_FILE_ID=your_excel_file_id_here
```

### 2. Security Considerations

- **NEVER** commit the `.env.local` file to version control
- The `.gitignore` file is already configured to exclude `.env*.local` files
- The API key is configured to be only used server-side and not exposed to the client
- When deploying to a hosting service, set these environment variables in the hosting platform's secure environment variables section

## Installation and Running the Application

1. Install dependencies:
```
npm install
```

2. Run the development server:
```
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000) with your browser to see the application

## Deployment Considerations

When deploying to platforms like GitHub Pages, Vercel, or Netlify:

1. **Never include your `.env.local` file in the repository**
2. Set up the environment variables in your hosting platform's dashboard
3. For GitHub Pages specifically, since it only hosts static files, you'll need to use a backend service or serverless functions to securely handle API calls that require your API key

## Security Best Practices

- Rotate API keys periodically
- Use the minimum required permissions for your API keys
- Monitor API usage for unexpected patterns
- Consider implementing rate limiting for API endpoints 