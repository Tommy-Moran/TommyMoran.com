# Integrating the HEART App with Your Squarespace Site

Since your main website (TommyMoran.com) is hosted on Squarespace, there are specific approaches you'll need to use to make the HEART app available at TommyMoran.com/HEART.

## Recommended Approach: Subdomain Method

For a Squarespace site, the cleanest approach is to use a subdomain (heart.tommymoran.com) and deploy the HEART app there.

### Step 1: Create a Separate GitHub Repository

1. Create a new repository on GitHub (e.g., `heart-app`)
2. Push the HEART app code to this repository

### Step 2: Set Up GitHub Pages for the App

1. In your heart-app repository, go to Settings → Pages
2. Set the source to GitHub Actions
3. Make sure your GitHub Actions workflow file (.github/workflows/deploy.yml) is present and correctly configured

### Step 3: Configure DNS for Your Subdomain

1. Log in to your domain registrar or DNS provider (likely through Squarespace)
2. Add a CNAME record:
   - Type: CNAME
   - Host: heart
   - Value: tommy-moran.github.io
   - TTL: Automatic or 3600

### Step 4: Set Up Custom Domain in GitHub Pages

1. In your GitHub repository Settings → Pages → Custom domain
2. Enter: `heart.tommymoran.com`
3. Save the changes
4. Check "Enforce HTTPS" once the DNS propagates (might take up to 24 hours)

### Step 5: Deploy the Backend on Render

1. Create a new Render web service
2. Connect to your GitHub repository
3. Configure as described in the README:
   - Build Command: `pip install -r scripts/requirements.txt`
   - Start Command: `cd scripts && gunicorn server:app`
   - Add the environment variable `AUDIT_PASSWORD`

### Step 6: Update the Frontend Configuration

Update the AUDIT_API_URL in your .env file or next.config.js to point to your Render backend URL.

## Alternative Approach: URL Mapping in Squarespace

If you strongly prefer having the app at TommyMoran.com/HEART instead of a subdomain, you can use Squarespace's URL Mapping feature:

### Step 1: Deploy the App as Described Above

Follow steps 1-5 from the subdomain approach to get the app running at heart.tommymoran.com.

### Step 2: Set Up URL Mapping in Squarespace

1. Log in to your Squarespace account
2. Go to Settings → Advanced → URL Mappings
3. Add the following mapping rule:

```
/HEART /heart.tommymoran.com
/HEART/* /heart.tommymoran.com/$1
```

This will redirect users who visit TommyMoran.com/HEART to your app deployed at heart.tommymoran.com.

### Step 3: Alternative - Use Squarespace Code Injection

If URL mapping doesn't work as expected, you can use Squarespace's Code Injection feature:

1. Create a blank page at /HEART in your Squarespace site
2. Go to Settings → Advanced → Code Injection
3. Add a script to redirect visitors:

```html
<script>
if (window.location.pathname.startsWith('/HEART')) {
  window.location.href = 'https://heart.tommymoran.com' + window.location.pathname.replace('/HEART', '');
}
</script>
```

## Which Approach Should You Choose?

For your Squarespace setup, I recommend the **subdomain approach** (heart.tommymoran.com) because:

1. It's cleaner technically and avoids complex redirects
2. It provides a clear separation between your main site and the app
3. It's less likely to break with Squarespace updates
4. It will perform better than URL mapping redirects

The URL mapping approach is possible but may introduce performance issues or break unexpectedly with Squarespace updates.

## Additional Squarespace-Specific Considerations

- **Squarespace Limitations**: Squarespace doesn't provide true subdirectory hosting for external apps
- **Analytics**: Set up separate Google Analytics for your app if tracking is important
- **Branding**: Use consistent styling between your main site and the app for a seamless experience
- **Mobile**: Ensure your app is fully responsive as Squarespace sites are mobile-optimized

## Next Steps

1. Choose your approach (subdomain recommended)
2. Follow the deployment steps
3. Test thoroughly on different devices and browsers
4. Monitor your app after launch for any issues 