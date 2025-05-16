# Deploying HEART App as a Separate Repository

This guide explains how to deploy the HEART app as a separate repository while making it accessible at TommyMoran.com/HEART.

## Option 1: Deploy as a Subdomain (heart.tommymoran.com)

This approach creates a subdomain for your HEART app.

### Step 1: Create a New GitHub Repository

1. Create a new repository on GitHub (e.g., `heart-app`)
2. Initialize it with a README file
3. Push the HEART app code to this repository

### Step 2: Configure GitHub Pages

1. Go to repository Settings → Pages
2. Configure source to be GitHub Actions
3. Keep the next.config.js settings WITHOUT the basePath (remove it if present)
4. Update the GitHub Actions workflow (.github/workflows/deploy.yml) to build without a base path

### Step 3: Configure Custom Subdomain

1. In repository Settings → Pages → Custom domain, add `heart.tommymoran.com`
2. Configure DNS with your domain provider:
   - Add a CNAME record for `heart` pointing to `tommy-moran.github.io`

### Step 4: Configure Backend on Render

Follow the instructions in heart-app/scripts/README.md.

### Step 5: Update Environment Variables

Add the GitHub repository secrets:
- `OPENAI_ASSISTANT_ID`
- `OPENAI_API_KEY`

### Step 6: Verify Deployment

Your app should be accessible at https://heart.tommymoran.com

## Option 2: Using a URL Rewriter for tommymoran.com/HEART

This approach uses a routing/rewrite rule at the domain level to redirect `/HEART` to a separate app.

### Step 1: Deploy the HEART App

1. Follow steps 1-5 from Option 1 to deploy the app to a subdomain or to another URL (e.g., heart-app.onrender.com)

### Step 2: Configure URL Rewriting

#### If Using Squarespace:

1. Log in to your Squarespace account
2. Go to Settings → Advanced → URL Mappings
3. Add a mapping rule to redirect `/HEART*` to your deployed app URL:

```
/HEART /{heart-app-url}/
/HEART/* /{heart-app-url}/$1
```

Replace `{heart-app-url}` with your actual deployment URL.

#### If Using Cloudflare:

1. Set up Page Rules or Cloudflare Workers to rewrite URLs from `/HEART/*` to your app URL

#### If Using a Custom Web Server:

Add rewrite rules to your web server configuration. For example, with NGINX:

```nginx
location /HEART {
  proxy_pass https://your-heart-app-url;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
}
```

### Step 3: CORS Configuration

Update your HEART app backend to allow requests from tommymoran.com:

```python
# In server.py
CORS(app, origins=["https://tommymoran.com"])
```

### Step 4: Verify Setup

Test that your app is accessible at https://tommymoran.com/HEART

## Which Option to Choose?

- **Option 1 (Subdomain)**: Cleaner implementation, easier to set up, but uses a subdomain instead of a path
- **Option 2 (URL Rewriting)**: More complex but achieves the exact URL structure you want

## Additional Considerations

- Make sure API URLs in your app account for the chosen deployment pattern
- Update any internal links to work correctly with your chosen URL structure
- Test thoroughly after deployment to ensure all functionality works as expected 