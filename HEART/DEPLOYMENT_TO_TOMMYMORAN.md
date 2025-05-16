# Deploying HEART App to TommyMoran.com/HEART

This guide provides step-by-step instructions for integrating the HEART application into your existing TommyMoran.com website as a subdirectory.

## Prerequisites

- Access to your TommyMoran.com GitHub repository
- Access to your web server configuration
- A Render account for backend deployment

## Step 1: Prepare the HEART App

1. Ensure your Next.js configuration has the correct `basePath` setting:

```javascript
// next.config.js
const nextConfig = {
  // Other config...
  basePath: '/HEART',
  // Environment variables...
}
```

2. Build and test the app locally to ensure it works with the basePath:

```bash
npm run build
npm run start
```

3. Visit http://localhost:3000/HEART to verify it works correctly

## Step 2: Set Up Backend on Render

1. Create a new Web Service on Render
   - Connect to your GitHub repository
   - Set the build command: `pip install -r scripts/requirements.txt`
   - Set the start command: `cd scripts && gunicorn server:app`
   - Add environment variables:
     - `AUDIT_PASSWORD`: Your secure password for accessing audit logs
     - `FLASK_ENV`: production

2. Deploy the backend and note the URL (e.g., https://heart-audit-api.onrender.com)

3. Update the HEART app's configuration to use this backend URL:

```javascript
// Next.js config or .env file
NEXT_PUBLIC_AUDIT_API_URL=https://heart-audit-api.onrender.com
```

## Step 3: Integrate with TommyMoran.com Repository

### Option A: Add to Existing Repository (Recommended)

1. Clone your TommyMoran.com repository:
```bash
git clone https://github.com/[your-username]/TommyMoran.com.git
cd TommyMoran.com
```

2. Create a directory for the HEART app:
```bash
mkdir -p HEART
```

3. Copy the HEART app files (excluding node_modules, .next, etc.):
```bash
cp -r path/to/heart-app/* HEART/
```

4. Configure the build process in your existing workflow or create a new one:

```yaml
# .github/workflows/deploy.yml (adjust according to your existing setup)
name: Deploy Website with HEART App

on:
  push:
    branches:
      - main

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      
      # Build your main website first (your existing steps)
      
      # Build HEART App
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: 18
          
      - name: Install HEART dependencies
        working-directory: ./HEART
        run: npm ci
        
      - name: Build HEART app
        working-directory: ./HEART
        run: npm run build
        env:
          NEXT_PUBLIC_AUDIT_API_URL: https://heart-audit-api.onrender.com
          OPENAI_ASSISTANT_ID: ${{ secrets.OPENAI_ASSISTANT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          
      # Copy HEART build output to your deployment directory
      - name: Copy HEART build output
        run: cp -r HEART/out/* public/HEART/
        
      # Deploy to your hosting (your existing deployment steps)
```

### Option B: Separate Repository with Server Configuration

If you're keeping the repositories separate, you'll need to configure your web server:

#### For Nginx:
```nginx
# In your Nginx config
location /HEART {
    alias /path/to/heart-app/out;
    try_files $uri $uri/ /HEART/_next/data/$uri /HEART/index.html =404;
}

# For API proxy if needed
location /HEART/api {
    proxy_pass https://heart-audit-api.onrender.com/api;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

#### For Apache:
```apache
# In your .htaccess or Apache config
RewriteEngine On
RewriteRule ^HEART/(.*)$ /path/to/heart-app/out/$1 [L]
```

## Step 4: Update CORS Settings in Backend

Add this to your Flask API to allow requests from your domain:

```python
# In your server.py file
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://tommymoran.com"])
```

## Step 5: Add Links to Your Main Site

Add navigation links to your main site to point to the HEART app:

```html
<a href="/HEART">HEART - Echo Appropriateness Tool</a>
```

## Step 6: Deploy and Test

1. Push your changes to GitHub to trigger deployment
2. Verify the app is accessible at https://tommymoran.com/HEART
3. Test the functionality, including:
   - Form submission
   - API integration
   - Results display
   - Admin access

## Troubleshooting

### Static Assets Not Loading
- Check that all asset URLs in the Next.js output include the correct basePath (/HEART)
- Verify that the server is correctly serving files from the HEART directory

### API Connection Issues
- Confirm CORS is properly configured
- Check that the frontend is using the correct API URL
- Verify the API is running on Render

### Routing Problems
- Ensure the Next.js app is properly configured for basePath
- Check server configurations for proper path handling
- For client-side routing issues, verify that Next.js Link components include the basePath

## Maintenance

- When updating the HEART app, rebuild and redeploy following the same process
- Monitor the Render backend for any issues
- Periodically back up your audit database 