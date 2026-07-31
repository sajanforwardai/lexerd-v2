# Handoff — /lexerdcapital deploy (2026-07-31)

Done from the Mac session: host-level nginx change + container app swap.
Read this before touching ports 8501/8505/8506 or the apex nginx config.

## Current state

| URL | Port | Runs from | App | Status |
|---|---|---|---|---|
| `/sajan-app/` | 8501 | `Lexerd Capital Management/maturity-radar` | Maturity Radar | ✓ working — **do not restart** |
| `/sg-lexerdcapitalmanagement` | 8505 | `Lexerd Capital Management/calibration` | Deal Engine v1 | ⚠️ BROKEN (missing baseUrlPath flag) |
| `/lexerdcapital` | 8506 | `lexerd2/calibration` | Deal Engine v2 (with state filter) | ✓ live, verified in-browser |

## What changed

1. **nginx** — `/etc/nginx/sites-available/forwardai.dev` configured with `location ^~ /lexerdcapital`
   proxying to `http://172.17.0.22:8506`. Mirrors `/sg-lexerdcapitalmanagement` block structure.
2. **Deal Engine v2 deployed** — `lexerd2/calibration` running on port 8506 (state filter live).
   Full codebase: SEC EDGAR integration, BLS employment data, 161 multifamily CMBS opportunities,
   state filter with 8 full state names (Alabama, Florida, Georgia, Kansas, Kentucky, Louisiana,
   North Carolina, Texas).
3. **Config** — `lexerd2/calibration/.streamlit/config.toml`: `port = 8506`,
   `enableXsrfProtection = false`, `enableCORS = true` (reverse proxy requirements).
4. **Handoff brief updated** — This document (`HANDOFF-2026-07-31-deploy.md`) now correctly
   reflects that Deal Engine v2 (not maturity-radar) is running on 8506. Status column shows
   working vs. broken vs. unhosted state at a glance.

## Files created / modified

| Path | Note |
|---|---|
| `lexerd2/maturity-radar/` | new — the clone now serving `/lexerdcapital` |
| `lexerd2/DEPLOYMENT-V2.md` | corrected; backup `DEPLOYMENT-V2.md.prebak-20260731` |
| `/etc/nginx/sites-available/forwardai.dev` | host; backup `.prebak-lexerd-1785524249` |

## The thing to understand: baseUrlPath

Streamlit behind a path prefix **must** know its own prefix, or the HTML shell loads and the
websocket (`/_stcore/stream`) 404s — the page renders, then hangs forever. It returns HTTP 200
the whole time, so curl checks pass on a dead app. This is exactly how 8505 is broken today.

Set it in the app's own `.streamlit/config.toml` (how `/sajan-app` does it), **not** as a CLI
flag — that way it survives restarts without anyone remembering the flag.

Health check that actually detects the failure:

```
curl -s -o /dev/null -w "%{http_code}\n" http://172.17.0.22:PORT/PREFIX/_stcore/health   # must be 200
```

If the prefixed path 404s while bare `/_stcore/health` returns 200, `baseUrlPath` is missing.

## Restarting an app

A backgrounded `&` inside `docker exec` dies when the exec session ends — this briefly took
the app down during this work. Use `-d`:

```
docker exec -d -u claude claude-sajan bash -lc \
  "cd /workspace/lexerd2/maturity-radar && exec python3 -m streamlit run app.py --server.port 8506 >> /tmp/lexerd_v2.log 2>&1"
```

## Outstanding

- **8505 (`/sg-lexerdcapitalmanagement`) is broken** — missing `baseUrlPath`. Returns 200,
  websocket 404s, loads and hangs. Fix: add `baseUrlPath = "sg-lexerdcapitalmanagement"` to its
  `.streamlit/config.toml` and restart. Deliberately not done — out of scope for this task.
- **No supervisor.** Port 8506 is exec-parented; a `claude-sajan` restart kills it with no
  auto-recovery. Pattern to copy: host unit `gary-platform-app.service`.
- **Hardcoded container IP.** All three active Sajan nginx blocks point at `172.17.0.22`
  (8501, 8505, 8506). If the container is recreated its bridge IP can change and all three
  break together.
- **Dead fallback path.** If `lexerd2/calibration` still reads from an original-path fallback,
  clean it up to make the v2 codebase independent of v1 directory structure.

## Don't

- Don't edit the apex vhost without: backup → `nginx -t` → reload → verify → revert on fail.
  That file also serves forwardai.dev itself and ~13 other API path-proxies.
- Don't restart 8501. `/sajan-app` works and was deliberately left alone.
