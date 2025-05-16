# HEART App Deployment Checklist

## 1. Prepare the HEART App
- [x] Add `basePath: '/HEART'` in next.config.js
- [ ] Test locally with `npm run build && npm run start`
- [ ] Verify app works at http://localhost:3000/HEART

## 2. Deploy Backend to Render
- [ ] Create new Web Service on Render
- [ ] Set build command: `pip install -r scripts/requirements.txt`
- [ ] Set start command: `cd scripts && gunicorn server:app`
- [ ] Add environment variable: `AUDIT_PASSWORD` (secure password)
- [ ] Deploy backend and note the URL

## 3. Update HEART App Configuration
- [ ] Set `NEXT_PUBLIC_AUDIT_API_URL` to your Render backend URL
- [ ] Set `OPENAI_ASSISTANT_ID` and `OPENAI_API_KEY` in your environment

## 4. Integrate with TommyMoran.com
- [ ] Clone your TommyMoran.com repository
- [ ] Create directory for HEART app (`mkdir -p HEART`)
- [ ] Copy HEART app files to new directory
- [ ] Add or update GitHub workflow to build HEART app
- [ ] Configure to copy built files to correct location in your deployment

## 5. Update Server Configuration (if needed)
- [ ] Add Nginx/Apache configuration for /HEART path
- [ ] Setup any required proxying for API requests

## 6. Final Steps
- [ ] Push changes to GitHub
- [ ] Verify deployment to TommyMoran.com/HEART
- [ ] Test all functionality:
  - [ ] Form submission
  - [ ] AI response
  - [ ] Case ID generation
  - [ ] Clipboard copying with ID
  - [ ] Admin panel access

## Important URLs
- Admin Panel: https://tommymoran.com/HEART/admin
- Backend API: https://heart-audit-api.onrender.com
- Main App: https://tommymoran.com/HEART

## Credentials
- Admin Panel Password: (Set in Render environment variables)
- OpenAI API Key: (Stored in GitHub repository secrets) 