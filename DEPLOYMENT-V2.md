# Lexerd v2 Deployment

**Status**: ⚠️ SUPERSEDED 2026-07-31 — port 8506 now serves the **Maturity Radar clone** (`lexerd2/maturity-radar`).
The Deal Engine v2 described below is intact at `lexerd2/calibration` but is **not currently hosted**.
See `HANDOFF-2026-07-31-deploy.md`.  
**Date**: 2026-07-31  
**Version**: v2.0.0 (7bb29bd)

## Access URLs

### Local (Development)
- **http://localhost:8506/lexerdcapital/** — Direct access from container (the `/lexerdcapital/` prefix is required; bare root 404s by design)
- **http://172.17.0.22:8506** — From container network

### Production (nginx configured 2026-07-31)
- **https://forwardai.dev/lexerdcapital** — ✅ live, but now serves the **Maturity Radar clone**, not this Deal Engine
- **https://forwardai.dev/sg-lexerdcapitalmanagement-v2** — Alternative (standard pattern)

## Running Instance

```
Port: 8506 — REASSIGNED
Now running: python3 -m streamlit run app.py --server.port 8506   (cwd /workspace/lexerd2/maturity-radar)
Deal Engine v2 (ui/app.py): NOT running — no port assigned
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

### Nginx Configuration — APPLIED 2026-07-31
The block below is live in `/etc/nginx/sites-available/forwardai.dev`
(backup: `forwardai.dev.prebak-lexerd-1785524249`). Corrected from the original draft:

```nginx
location ^~ /lexerdcapital {
    proxy_pass http://172.17.0.22:8506;   # container IP. NOT localhost:
                                          # nothing listens on the HOST's 8506.
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
| Sajan App (Maturity Radar) | 8501 | /sajan-app | ✓ Running |
| Lexerd v1 (Deal Engine) | 8505 | /sg-lexerdcapitalmanagement | ⚠️ Running but BROKEN — missing `baseUrlPath`, websocket 404s |
| Maturity Radar clone | 8506 | /lexerdcapital | ✓ Running (live) |
| Deal Engine v2 | — | — | Intact at `lexerd2/calibration`, unhosted |

## Test Commands

```bash
# Test v2 is running
curl -I http://localhost:8506/lexerdcapital/

# View logs
tail -f /tmp/lexerd_v2.log

# Restart whatever is on 8506 (currently Maturity Radar clone)
# NOTE: a backgrounded & inside docker exec DIES with the exec session. Use -d.
docker exec -u claude claude-sajan pkill -f -- "--server.port 8506"
docker exec -d -u claude claude-sajan bash -lc \
  "cd /workspace/lexerd2/maturity-radar && exec python3 -m streamlit run app.py --server.port 8506 >> /tmp/lexerd_v2.log 2>&1"

# Subpath health check — MUST be 200, or the app loads and never connects:
curl -s -o /dev/null -w "%{http_code}\n" http://172.17.0.22:8506/lexerdcapital/_stcore/health
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

1. ~~Configure Nginx~~ — ✅ done 2026-07-31 (target is `172.17.0.22:8506`, not localhost)
2. ~~Test Production URL~~ — ✅ verified in-browser; renders Maturity Radar
3. **Decide where Deal Engine v2 goes** — it is unhosted; needs its own port + nginx block if it should stay reachable
4. **Fix Lexerd v1 (8505)** — add `baseUrlPath = "sg-lexerdcapitalmanagement"` to its `.streamlit/config.toml`
3. **GitHub Repo**: Push to private repo (awaiting URL)
4. **Feature Development**: Use branching strategy (spec → TDD → gate → merge)

## Subpath deployment — the rule

Streamlit behind a path prefix MUST know its own prefix, set in the app's own
`.streamlit/config.toml`:

```toml
[server]
port = 8506
baseUrlPath = "lexerdcapital"
```

Without it the HTML shell loads, `/_stcore/stream` 404s, and the page renders then
hangs forever — while returning HTTP 200 the whole time, so curl checks look healthy.
Set it in config, not as a CLI flag, so it survives restarts.

---

Built with ForwardAI praxis build doctrine  
*Spec-gate → TDD worktree-swarm → two-reviewer gate → interactive deploy*
