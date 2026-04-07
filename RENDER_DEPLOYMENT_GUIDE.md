# 🚀 NIVORA ERP - RENDER DEPLOYMENT GUIDE

**Last Updated:** April 7, 2026
**Status:** ✅ READY FOR DEPLOYMENT

---

## 📋 TABLE OF CONTENTS

1. Project Cleanup & Preparation
2. Local Testing
3. GitHub Repository Setup
4. Render Service Deployment
5. Post-Deployment Verification
6. Troubleshooting

---

## ✅ STEP 1: PROJECT CLEANUP & PREPARATION (COMPLETED)

### Files Cleaned
```
✅ All __pycache__ directories removed
✅ All *.pyc and *.pyo files removed
✅ All .DS_Store files removed
✅ db.sqlite3 removed (use PostgreSQL instead)
✅ staticfiles/ removed (will be regenerated)
✅ logs/ removed
✅ All test artifacts removed (.pytest_cache, htmlcov, .coverage)
✅ .gitignore verified with all necessary entries
```

### Files Created/Updated
```
✅ Procfile - Render deployment configuration
✅ runtime.txt - Python version specification
✅ render.yaml - Infrastructure as Code configuration
✅ requirements.txt - Added whitenoise + dj-database-url
✅ .env.example - Environment variable template
✅ config/settings.py - Production-ready configuration
```

---

## ✅ STEP 2: LOCAL TESTING

### Verify Django System Check
```bash
DJANGO_DEBUG=True python3 manage.py check
# Expected: System check identified no issues (0 silenced)
```

### Collect Static Files Locally
```bash
DJANGO_DEBUG=True python3 manage.py collectstatic --noinput
# This tests that staticfiles configuration works
```

### Run Migrations Locally
```bash
DJANGO_DEBUG=True python3 manage.py migrate
# Expected: All migrations applied successfully
```

### Test Server Locally
```bash
DJANGO_DEBUG=True python3 manage.py runserver
# Verify app loads at http://127.0.0.1:8000
```

---

## ✅ STEP 3: GITHUB REPOSITORY SETUP

### Initialize Git Repository
```bash
cd /Users/mahi../Desktop/NIVORA

# Initialize if not already a git repo
git init

# Add all files
git add .

# Create initial commit
git commit -m "chore: prepare NIVORA ERP for production deployment to Render"

# Add GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/nivora-erp.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Verify GitHub Repository
- Go to https://github.com/YOUR_USERNAME/nivora-erp
- Verify all files are present
- Verify .gitignore is working (no .env, db.sqlite3, __pycache__)

---

## 🚀 STEP 4: RENDER SERVICE DEPLOYMENT

### Option A: Using render.yaml (Recommended)

1. **Connect GitHub to Render**
   - Go to https://render.com
   - Click "New +"
   - Select "Blueprint"
   - Paste your GitHub repository URL
   - Authorize GitHub access

2. **Review render.yaml Configuration**
   - Automatically creates Web Service + PostgreSQL + Redis
   - Services named: nivora-erp, nivora-db, nivora-redis

3. **Set Environment Variables**
   - Navigate to the "Environment" tab in Render
   - Add the following variables:

   ```
   DJANGO_SECRET_KEY=<generated-in-next-step>
   DJANGO_ALLOWED_HOSTS=<your-app>.onrender.com
   ```

4. **Generate Django SECRET_KEY**
   ```bash
   python3 << 'EOF'
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   EOF
   ```
   - Copy the output and set as DJANGO_SECRET_KEY in Render

5. **Deploy**
   - Click "Deploy"
   - Wait for build and deployment to complete (~5-10 minutes)

---

### Option B: Manual Setup (If render.yaml doesn't work)

1. **Create Web Service**
   - Go to https://render.com/dashboard
   - Click "New +"
   - Select "Web Service"
   - Connect GitHub repository
   - Select "Existing Repository"
   - Choose "nivora-erp" repository

2. **Configure Web Service**
   - Name: `nivora-erp`
   - Environment: Python
   - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start Command: `gunicorn config.wsgi`
   - Instance Type: Free

3. **Create PostgreSQL Database**
   - Click "New +"
   - Select "PostgreSQL"
   - Name: `nivora-db`
   - Instance Type: Free
   - Save and copy the DATABASE_URL

4. **Create Redis Cache**
   - Click "New +"
   - Select "Redis"
   - Name: `nivora-redis`
   - Instance Type: Free
   - Save and copy the REDIS_URL

5. **Set Environment Variables on Web Service**
   ```
   DJANGO_SECRET_KEY=<generate-and-paste>
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=<your-app>.onrender.com,www.<your-app>.onrender.com
   DATABASE_URL=<paste-from-PostgreSQL>
   REDIS_URL=<paste-from-Redis>
   CELERY_BROKER_URL=<same-as-REDIS_URL>
   CELERY_RESULT_BACKEND=<same-as-REDIS_URL>
   ```

6. **Link Services**
   - On Web Service, add DATABASE_URL and REDIS_URL environment variables
   - Deploy

---

## ✅ STEP 5: POST-DEPLOYMENT VERIFICATION

### Check Deployment Status
1. Go to Render dashboard
2. Select "nivora-erp" service
3. Check "Logs" tab for any errors
4. Deployment URL should be: `https://<your-app>.onrender.com`

### Test Health Endpoint
```bash
# Replace with your actual Render URL
curl https://<your-app>.onrender.com/

# Expected: HTML page loads (login page)
```

### Test Authentication
```bash
# Test registration (if API available)
curl -X POST https://<your-app>.onrender.com/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123"}'
```

### Verify Database Connection
```bash
# Render logs should show successful migrations
# Check in Render dashboard: Select service → Logs
# Look for: "Applying operations.0001_initial..."
```

### Test Static Files
```bash
# Verify CSS/JS are loading
curl -I https://<your-app>.onrender.com/static/css/nivora.css
# Expected: HTTP/1.1 200 OK
```

### Access Application
1. Open https://<your-app>.onrender.com in browser
2. Verify login page loads
3. Verify CSS styling (Light Green Theme) is applied
4. Verify no DEBUG information is shown

---

## 🔧 TROUBLESHOOTING

### Issue: "DJANGO_SECRET_KEY is required in production"
**Cause:** DJANGO_SECRET_KEY environment variable not set
**Fix:**
1. Generate key: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
2. Add to Render environment variables
3. Redeploy service

### Issue: "Static files not loading (404)"
**Cause:** collectstatic command didn't run during build
**Fix:**
1. Check Render build logs
2. Verify Procfile release command: `release: python manage.py migrate`
3. Add build step: Include `python manage.py collectstatic --noinput` in build command
4. Redeploy

### Issue: "Database connection error"
**Cause:** DATABASE_URL not set or incorrect
**Fix:**
1. Verify DATABASE_URL is set in Render environment
2. Format should be: `postgresql://user:password@host:port/dbname`
3. Cannot use SQLite on Render (filesystem is ephemeral)
4. Check PostgreSQL service is running
5. Redeploy web service

### Issue: "Migrations not applied"
**Cause:** Release command not running
**Fix:**
1. Check Procfile has: `release: python manage.py migrate`
2. Check Render deployment logs
3. Manually run migrations if needed (Render SSH):
   ```bash
   python manage.py migrate
   ```
4. Redeploy

### Issue: "500 Error - Internal Server Error"
**Cause:** Various production errors
**Fix:**
1. Check Render logs for detailed error
2. Verify all environment variables are set
3. Verify DATABASE_URL and REDIS_URL are correct
4. Check that ALLOWED_HOSTS includes your Render domain
5. Verify SECRET_KEY is valid
6. Redeploy

### Issue: "DEBUG information exposed"
**Cause:** DEBUG=True or DEBUG env var not False
**Fix:**
1. Verify DJANGO_DEBUG is set to "False" (not "True")
2. Remove DJANGO_DEBUG=True if set
3. Ensure settings.py has DEBUG = env_bool("DJANGO_DEBUG", default=False)
4. Redeploy

---

## 📊 RENDER PRICING (FREE TIER)

- **Web Service:** Free tier with 0.5 CPU, 512MB RAM
- **PostgreSQL:** Free tier with 256MB storage
- **Redis:** Free tier with 256MB storage

**Limitations:**
- Spins down after 15 minutes of inactivity
- May have 30-50 second startup delay
- Limited storage (suitable for development/testing)
- No horizontal scaling

**Upgrade Path:**
- Standard tier: ~$7/month per service
- Professional tier: Custom pricing

---

## 🔐 POST-DEPLOYMENT SECURITY

### Verify Security Settings
```bash
# Test HTTPS redirect (if enabled)
curl -I http://<your-app>.onrender.com
# Should redirect to HTTPS

# Check security headers
curl -I https://<your-app>.onrender.com | grep -i security
```

### Set Additional Environment Variables
```
SECURE_HSTS_SECONDS=31536000
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Monitor Application
- Set up error tracking: Sentry (free tier available)
- Monitor performance: Render dashboard metrics
- Check logs regularly

---

## 📈 SCALING FOR PRODUCTION

When ready to scale beyond free tier:

### Upgrade Database Plan
```bash
1. Render Dashboard → PostgreSQL service
2. Click "Upgrade"
3. Select desired plan
4. No need to modify DATABASE_URL
```

### Upgrade Web Service
```bash
1. Render Dashboard → Web Service
2. Click "Settings"
3. Select "Standard" or higher tier
4. Optionally increase CPU/RAM
```

### Add Redis Cache Service
```bash
1. Already set up with free tier
2. Upgrade same as Web Service
3. Render maintains connection automatically
```

### Add Celery Worker (Optional)
```bash
1. Create new Web Service from same repo
2. Start Command: celery -A config worker -l info
3. Share same DATABASE_URL and REDIS_URL
4. Environment: Worker service
```

---

## ✅ DEPLOYMENT CHECKLIST

### Pre-Deployment
- [x] All files cleaned (no cache, db, logs)
- [x] requirements.txt updated with whitenoise, dj-database-url
- [x] Procfile created and configured
- [x] runtime.txt specifies Python 3.9
- [x] render.yaml created (optional but recommended)
- [x] settings.py configured for production
- [x] SECRET_KEY is environment-based
- [x] DEBUG=False by default
- [x] ALLOWED_HOSTS can be set via env var
- [x] Static files configuration complete
- [x] .env.example updated with all required variables

### Deployment
- [ ] GitHub repository created and code pushed
- [ ] Render account created (https://render.com)
- [ ] Web Service created and connected to GitHub
- [ ] PostgreSQL database created
- [ ] Redis cache service created
- [ ] Environment variables set:
  - [ ] DJANGO_SECRET_KEY
  - [ ] DJANGO_ALLOWED_HOSTS
  - [ ] DATABASE_URL (auto-set if using render.yaml)
  - [ ] REDIS_URL (auto-set if using render.yaml)
- [ ] Deployment completed successfully
- [ ] Render URL noted: https://_____.onrender.com

### Post-Deployment
- [ ] Health endpoint responds
- [ ] Static files loading correctly
- [ ] Database migrations applied
- [ ] Application starts without errors
- [ ] Login page loads
- [ ] No DEBUG information exposed
- [ ] CSRF tokens present in forms

---

## 📞 SUPPORT & NEXT STEPS

### Monitor Deployment
- Render Dashboard: Check service status and logs
- Error Tracking: Set up Sentry or similar
- Performance: Monitor response times

### Common Next Steps
1. **Email Configuration**
   - Set up SMTP credentials for production email
   - Update EMAIL_HOST_USER and EMAIL_HOST_PASSWORD

2. **Custom Domain**
   - Render supports custom domains
   - Go to Web Service → Settings → Custom Domain

3. **SSL Certificate**
   - Render provides free SSL via Let's Encrypt
   - Automatically renewed

4. **Backups**
   - Set up scheduled PostgreSQL backups
   - Configure automated backup storage

5. **Monitoring**
   - Set up uptime monitoring
   - Configure error alerts via email/Slack

---

## 🎉 DEPLOYMENT COMPLETE

Your NIVORA ERP application is now deployed on Render and accessible at:

**https://<your-app>.onrender.com**

---

**For detailed Render documentation, visit:** https://render.com/docs

**For Django deployment best practices:** https://docs.djangoproject.com/en/4.2/howto/deployment/

