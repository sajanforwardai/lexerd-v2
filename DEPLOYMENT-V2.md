# Lexerd v2 Deployment

**Status**: ✅ Live on port 8506  
**Date**: 2026-07-31  
**Version**: v2.0.0 (7bb29bd)

## Access URLs

### Local (Development)
- **http://localhost:8506** — Direct access from container
- **http://172.17.0.22:8506** — From container network

### Production (Requires Nginx Config)
- **https://forwardai.dev/lexerdcapital** — Target URL (configure nginx)
- **https://forwardai.dev/sg-lexerdcapitalmanagement-v2** — Alternative (standard pattern)

## Running Instance

```
Port: 8506
Process: python3 -m streamlit run ui/app.py --server.port 8506
PID: 1064905
Status: ✓ Running (HTTP 200 OK)
```

## Features Live

✅ **Opportunities Tab**
- State filter with 8 full state names (Alabama, Florida, Georgia, Kansas, Kentucky, Louisiana, North Carolina, Texas)
- 161 multifamily CMBS opportunities
- Tier 1/2/3 ranking by maturity
- Real DSCR, LTV, maturity dates
- Clickable SEC filing links
- CSV/Excel/JSON export

✅ **Properties Tab**
- Batch CSV upload & scoring
- 3M Model scoring (Market 30%, Model 40%, Management 30%)
- Results in Analytics tab

✅ **Analytics Tab**
- Score distribution charts
- Risk breakdown by grade
- Summary statistics

✅ **Professional Dashboard**
- SaaS design patterns
- Responsive layout
- Real-time filtering

## Deployment Notes

### Nginx Configuration Needed
To make Lexerd v2 accessible at `forwardai.dev/lexerdcapital`:

```nginx
location /lexerdcapital {
    proxy_pass http://localhost:8506;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### Current Working Instances

| App | Port | URL | Status |
|-----|------|-----|--------|
| Lexerd v1 | 8505 | /sg-lexerdcapitalmanagement | ✓ Running |
| Lexerd v2 | 8506 | /lexerdcapital (pending) | ✓ Running |
| Sajan App | 8501 | /sajan-app | ✓ Running |

## Test Commands

```bash
# Test v2 is running
curl -I http://localhost:8506

# View logs
tail -f /tmp/lexerd_v2.log

# Restart v2
pkill -f "streamlit.*8506"
cd /workspace/lexerd2/calibration
streamlit run ui/app.py --server.port 8506 &
```

## Data Sources

- **Freddie Mac B3**: 41% market coverage (GSE channel)
- **SEC CMBS Filings**: 40-50% market coverage (private-label channel)
- **BLS Employment**: 20+ MSA codes with monthly updates
- **Census/Zillow**: Ready for integration

## Recent Changes

**Commit 7bb29bd** - Add state filter dropdown
- Multiselect with 8 full state names (no abbreviations)
- Filters opportunities in all tiers
- Shows filtered count in exports
- All states selected by default

**Commit 7ded69a** - Full v1 codebase copy
- Complete calibration package
- All data pipelines
- 100+ unit tests
- 6 feature specifications

## Next Steps

1. **Configure Nginx**: Add reverse proxy for `/lexerdcapital` → `localhost:8506`
2. **Test Production URL**: Verify https://forwardai.dev/lexerdcapital works
3. **GitHub Repo**: Push to private repo (awaiting URL)
4. **Feature Development**: Use branching strategy (spec → TDD → gate → merge)

---

Built with ForwardAI praxis build doctrine  
*Spec-gate → TDD worktree-swarm → two-reviewer gate → interactive deploy*
