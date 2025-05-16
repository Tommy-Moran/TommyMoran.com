# Deploying HEART App to TommyMoran.com/HEART

This guide explains how to integrate the HEART app into your existing TommyMoran.com repository.

## Step 1: Prepare the HEART App

1. Update `next.config.js` to use the `/HEART` base path (already done).

2. Test the app locally with the base path:
   ```
   npm run dev
   ```
   And verify it works at `http://localhost:3000/HEART`.

## Step 2: Integrate with TommyMoran.com Repository

1. Clone your TommyMoran.com repository:
   ```bash
   git clone https://github.com/Tommy-Moran/TommyMoran.com.git
   cd TommyMoran.com
   ```

2. Create a new directory called `HEART` in your repository:
   ```bash
   mkdir -p HEART
   ```

3. Copy the HEART app files:
   - Copy all files from this project's `heart-app` directory to the `HEART` directory in your TommyMoran.com repository.
   - Copy the backend files from this project's `heart-app/scripts` directory to the root of your TommyMoran.com repository (or if you already have a `scripts` directory, copy them there).

4. Update your main repository's `.gitignore` to include Next.js build files:
   ```
   # Next.js
   .next/
   out/
   node_modules/
   ```

5. Update the GitHub Actions workflow:
   - If you have an existing GitHub Actions workflow, update it to include building the HEART app.
   - If not, create a new file at `.github/workflows/deploy-heart.yml` in your TommyMoran.com repository.

## Step 3: Configure GitHub Actions Workflow

Create or update your GitHub Actions workflow to build and deploy the HEART app:

```yaml
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

      # Build your existing website (if applicable)
      # This depends on how your main website is built

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
        run: |
          npm run build
          touch out/.nojekyll
        env:
          NEXT_PUBLIC_AUDIT_API_URL: https://heart-audit-api.onrender.com
          OPENAI_ASSISTANT_ID: ${{ secrets.OPENAI_ASSISTANT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      # Copy HEART build output to your main website directory
      - name: Copy HEART build output
        run: |
          mkdir -p public/HEART
          cp -r HEART/out/* public/HEART/

      # Deploy to GitHub Pages
      - name: Deploy to GitHub Pages
        uses: JamesIves/github-pages-deploy-action@v4
        with:
          folder: public
          branch: gh-pages

## Step 4: Configure Backend on Render

The backend deployment steps remain the same as in the original DEPLOYMENT.md:

1. Create a new Web Service on Render
2. Connect to your GitHub repository
3. Configure:
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn server:app`
   - Environment variables:
     - `AUDIT_PASSWORD`: A secure password for accessing audit logs
     - `FLASK_ENV`: `production`

## Step 5: Update GitHub Repository Secrets

Add the following secrets to your TommyMoran.com GitHub repository:
- `OPENAI_ASSISTANT_ID`: Your OpenAI Assistant ID
- `OPENAI_API_KEY`: Your OpenAI API key

## Step 6: Commit and Push Changes

Commit all your changes and push to your repository:
```bash
git add .
git commit -m "Integrate HEART App"
git push
```

GitHub Actions will automatically build and deploy your website with the HEART app.

## Step 7: Verify Deployment

After deployment completes, verify that your HEART app is accessible at:
- https://tommymoran.com/HEART

## Troubleshooting

### App Not Visible
- Ensure the `basePath` is correctly set in your Next.js config
- Check that the build output is being copied to the correct directory
- Verify your GitHub Pages configuration is correct

### Backend Issues
- Verify that your Render backend is running
- Check CORS settings if you encounter API errors 