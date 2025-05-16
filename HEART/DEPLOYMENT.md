# HEART App Deployment Guide

This guide explains how to deploy the HEART (Hospital Echo Appropriateness Request Tool) application to GitHub Pages with the backend on Render.

## Overview

The deployment involves two main components:
1. **Frontend**: NextJS app deployed to GitHub Pages
2. **Backend**: Flask API deployed to Render

## Backend Deployment (Render)

1. **Create a Render account** at [render.com](https://render.com/) if you don't have one already.

2. **Connect your GitHub account** to Render.

3. **Create a new Web Service**:
   - Click "New" and select "Web Service"
   - Connect your GitHub repository
   - Find and select your repository (e.g., `Tommy-Moran/TommyMoran.com`)

4. **Configure the Web Service**:
   - Name: `heart-audit-api` (or your preferred name)
   - Environment: `Python`
   - Region: Choose the one closest to your users
   - Branch: `main` (or your deployment branch)
   - Build Command: `pip install -r scripts/requirements.txt`
   - Start Command: `cd scripts && gunicorn server:app`
   - Add the following environment variables:
     - `AUDIT_PASSWORD`: A secure password for accessing audit logs
     - `FLASK_ENV`: `production`

5. **Create the Web Service** and wait for the deployment to complete.

6. **Note the service URL** (e.g., `https://heart-audit-api.onrender.com`)

## Frontend Deployment (GitHub Pages)

### Step 1: Configure environment

1. **Update your Next.js config** to include the backend URL:
   - In `next.config.js`, ensure the `NEXT_PUBLIC_AUDIT_API_URL` points to your Render service URL

### Step 2: Build for GitHub Pages

1. **Update your repository settings**:
   - Go to your GitHub repository settings
   - Navigate to "Pages"
   - Set the source to "GitHub Actions"

2. **Create a GitHub Actions workflow**:
   - Create a file at `.github/workflows/deploy.yml`
   - Use the following content:

```yaml
name: Deploy to GitHub Pages

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

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: 18

      - name: Install dependencies
        working-directory: ./heart-app
        run: npm ci

      - name: Build
        working-directory: ./heart-app
        run: |
          npm run build
          touch out/.nojekyll
        env:
          NEXT_PUBLIC_AUDIT_API_URL: https://heart-audit-api.onrender.com
          OPENAI_ASSISTANT_ID: ${{ secrets.OPENAI_ASSISTANT_ID }}

      - name: Deploy
        uses: JamesIves/github-pages-deploy-action@v4
        with:
          folder: heart-app/out
          branch: gh-pages
```

3. **Add the necessary secrets** to your GitHub repository:
   - Go to your repository settings
   - Navigate to "Secrets and variables" → "Actions"
   - Add the following secrets:
     - `OPENAI_ASSISTANT_ID`: Your OpenAI Assistant ID

4. **Commit and push** your changes to the main branch

5. **Monitor the GitHub Actions workflow** to ensure it completes successfully

### Step 3: Configure DNS for Custom Domain

If you want to use your custom domain (TommyMoran.com/HEART):

1. **Configure custom domain in GitHub Pages**:
   - Go to repository settings → Pages
   - Under "Custom domain", enter your domain (e.g., `tommymoran.com`)
   - Save the changes

2. **Configure DNS settings** with your domain provider:
   - Add a CNAME record for `heart.tommymoran.com` pointing to `tommy-moran.github.io`
   - Or, to use a subdirectory like `tommymoran.com/HEART`:
     - Set up your main domain to point to GitHub Pages
     - Ensure your GitHub Pages repository is published at the root

## Accessing Admin Panel

Once deployed, you can access the admin panel at:
- `https://tommymoran.com/HEART/admin` (or your specific domain)

You'll need to enter the password you set in the Render environment variables (`AUDIT_PASSWORD`).

## Troubleshooting

### CORS Issues
If you encounter CORS issues:
1. Verify that CORS is properly configured in the Flask app
2. Ensure the correct API URL is being used in the frontend

### Database Issues
The backend uses SQLite, which stores data in a file. On Render:
- The database file will be created in the deployment directory
- Note that Render's free tier uses ephemeral disks, so data may be lost on redeploys
- For production, consider upgrading to a paid plan or using a persistent database service

### API Not Reachable
If your API is not reachable:
1. Check that the Render service is running
2. Verify the URL is correct in your Next.js configuration
3. Test the API directly using Postman or curl 