#!/bin/bash

# Create a temporary directory for deployment
mkdir -p deploy
mkdir -p deploy/EchoApp

# Copy main website files
cp index.html deploy/
cp styles.css deploy/
cp script.js deploy/
cp profile-image.jpg deploy/

# Copy Echo App files
cp -r EchoApp/* deploy/EchoApp/

# Create a README with deployment instructions
cat > deploy/README.md << 'EOF'
# Deployment Instructions for SquareSpace

## Main Website
1. Log in to your SquareSpace account
2. Go to Pages
3. Edit your main page
4. Use the "Code" block to paste the contents of index.html
5. Upload the following files to SquareSpace:
   - styles.css
   - script.js
   - profile-image.jpg

## Echo App
1. Go to Pages
2. Create a new "Not Linked" page called "EchoApp"
3. In the page settings, set the URL to "EchoApp"
4. Use the "Code" block to paste the contents of EchoApp/index.html
5. Upload the following directories to SquareSpace:
   - EchoApp/styles/
   - EchoApp/js/
   - EchoApp/images/

## Important Notes
- Make sure to enable custom code in your SquareSpace settings
- Test all navigation links after deployment
- Check that all assets are loading correctly
EOF

echo "Deployment files have been prepared in the 'deploy' directory."
echo "Please follow the instructions in deploy/README.md to complete the deployment." 