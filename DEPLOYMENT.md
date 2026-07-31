# Deployment Guide — Lexerd Deal Engine

**Target:** `https://forwardai.dev/sg-lexerdcapitalmanagement`  
**Repository:** `https://github.com/sajanforwardai/sg-lexerdcapitalmanagement`  
**Status:** Ready for deployment

---

## Step 1: Push to GitHub

### From Windows (PowerShell)

```powershell
cd "C:\path\to\Lexerd Capital Management"

# Verify git is initialized
git status

# Add GitHub remote
git remote add origin https://github.com/sajanforwardai/sg-lexerdcapitalmanagement.git

# Push to GitHub
git push -u origin master
```

You'll be prompted for GitHub credentials. Use:
- Username: `sajanforwardai`
- Password: GitHub Personal Access Token (or password if 2FA not enabled)

### From Linux/Mac

```bash
cd /workspace/Lexerd\ Capital\ Management

git remote add origin https://github.com/sajanforwardai/sg-lexerdcapitalmanagement.git
git push -u origin master
```

---

## Step 2: Deploy to forwardai.dev

Once the code is pushed to GitHub, the deployment can be triggered via:

### Option A: forwardai.dev Dashboard
1. Go to `forwardai.dev/admin/deployments`
2. Click "New Deployment"
3. Select repository: `sajanforwardai/sg-lexerdcapitalmanagement`
4. Branch: `master`
5. Deployment spec: Auto-detect from `deploy.spec.json`
6. Click "Deploy"

### Option B: CLI (if available)

```bash
forwardai deploy --repo=sajanforwardai/sg-lexerdcapitalmanagement --spec=deploy.spec.json
```

### Option C: Manual Deployment to Coolify/Traefik

Use the `deploy.spec.json` manifest with your container orchestration platform:

```bash
# Convert to Docker Compose or Kubernetes manifest
forwardai deploy generate --spec=deploy.spec.json --format=docker-compose

# Deploy
docker-compose up -d
```

---

## Deployment Manifest

**File:** `deploy.spec.json`

```json
{
  "name": "sg-lexerdcapitalmanagement",
  "displayName": "Lexerd Deal Engine — Stage 1",
  "type": "streamlit",
  "repo": "https://github.com/sajanforwardai/sg-lexerdcapitalmanagement",
  "workingDirectory": "calibration",
  "entrypoint": "ui/app.py",
  "port": 8501,
  "resources": {
    "cpu": "1",
    "memory": "512Mi"
  }
}
```

**Key fields:**
- `type: streamlit` — Uses Streamlit runtime
- `workingDirectory: calibration` — Runs from calibration folder
- `entrypoint: ui/app.py` — Runs `streamlit run ui/app.py`
- `port: 8501` — Streamlit default port
- `resources` — CPU & memory allocation (1 CPU, 512MB RAM minimum)

---

## Post-Deployment Verification

### 1. Health Check
```bash
curl https://forwardai.dev/sg-lexerdcapitalmanagement/
# Should return 200 OK (Streamlit HTML)
```

### 2. Feature Test
- Go to `https://forwardai.dev/sg-lexerdcapitalmanagement/`
- Click "Score San Marco Village"
- Verify result shows Grade B (75.6/100)

### 3. Batch Upload Test
- Upload `sample_data.csv`
- Score all 10 properties
- Verify CSV download works

### 4. Monitor Logs
```bash
forwardai logs sg-lexerdcapitalmanagement --follow
```

---

## Troubleshooting

### "Module not found: models"
**Cause:** Working directory not set correctly  
**Fix:** Ensure `workingDirectory: calibration` in deploy.spec.json

### "Streamlit not found"
**Cause:** Dependencies not installed  
**Fix:** Ensure `requirements.txt` is in calibration directory and lists streamlit

### "Port 8501 already in use"
**Cause:** Another instance running  
**Fix:** Change port in deploy.spec.json or stop conflicting container

### "Connection refused"
**Cause:** Deployment not ready  
**Fix:** Wait 30-60 seconds, check health check logs

---

## Environment Variables

The deployment sets these automatically:

```
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
PYTHONUNBUFFERED=1
```

To add custom env vars, update `deploy.spec.json`:

```json
"environment": {
  "STREAMLIT_SERVER_PORT": "8501",
  "CUSTOM_VAR": "value"
}
```

---

## Monitoring & Logs

### View Deployment Status
```bash
forwardai status sg-lexerdcapitalmanagement
```

### View Logs
```bash
forwardai logs sg-lexerdcapitalmanagement --tail=100
```

### View Metrics
- CPU usage
- Memory usage
- Request latency
- Error rate

All available on `forwardai.dev/admin/deployments/sg-lexerdcapitalmanagement`

---

## Rollback

If deployment fails or needs rollback:

```bash
# Rollback to previous version
forwardai rollback sg-lexerdcapitalmanagement --version=1.0.0

# Or redeploy from main branch
git push origin feature-branch:master
# Wait for auto-redeploy
```

---

## Update/Redeployment

To redeploy after code changes:

```bash
# On your local machine
git add -A
git commit -m "Update: <change description>"
git push origin master

# Deployment triggers automatically (if webhook configured)
# Or manually trigger via CLI:
forwardai deploy --repo=sajanforwardai/sg-lexerdcapitalmanagement
```

---

## Cost Estimation

| Component | Cost | Notes |
|-----------|------|-------|
| Compute (512MB RAM, 1 CPU) | ~$5–10/month | Minimal load |
| Storage (code repo) | Free | GitHub free tier |
| Bandwidth | ~$0.10/GB | Minimal (dashboard is lightweight) |
| **Total** | **~$5–10/month** | Scales up with traffic |

---

## Security

### Environment Variables
- No secrets in code
- Use forwardai secrets manager for credentials
- Rotate tokens regularly

### Access Control
- Restrict dashboard to internal IP or VPN (if needed)
- Monitor access logs
- Alert on unusual activity

### Updates
- Regularly update dependencies
- Subscribe to security advisories
- Apply patches promptly

---

## Support

For deployment issues:
1. Check logs: `forwardai logs sg-lexerdcapitalmanagement`
2. Check health: `curl https://forwardai.dev/sg-lexerdcapitalmanagement/`
3. Open issue: `https://github.com/sajanforwardai/sg-lexerdcapitalmanagement/issues`

---

*Last updated: July 31, 2026*  
*Deployment ready for Stage 1*
