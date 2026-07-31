# Lexerd v1 → v2 Migration Guide

## Overview
v2 is a complete copy of v1, allowing independent development and deployment in parallel.

## Key Differences

| Aspect | v1 | v2 |
|--------|----|----|
| Directory | `/workspace/Lexerd Capital Management` | `/workspace/lexerd2` |
| Streamlit Port | 8505 | 8506 |
| Deployment URL | `/sg-lexerdcapitalmanagement` | `/sg-lexerdcapitalmanagement-v2` |
| GitHub Repo | `sg-lexerdcapitalmanagement` | `lexerd2-private` (configure) |
| Status | Production | Development/Testing |

## Running v2 Locally

```bash
cd /workspace/lexerd2/calibration
streamlit run ui/app.py --server.port 8506
```

Then visit: `http://localhost:8506`

## Deploying v2

v2 follows ForwardAI praxis:
1. **Spec-gate**: Write feature spec
2. **TDD worktree-swarm**: Implement in isolated branches
3. **Two-reviewer gate**: Run `praxis-gate` before merge
4. **Interactive deploy**: Push to master → auto-deploy

See `/workspace/.swarm/praxis/README.md` for full build doctrine.

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Implement with tests
# Run praxis-gate
bash /workspace/.swarm/praxis/toolkit/bin/praxis-gate.sh

# Commit & push
git push origin feature/your-feature

# Create PR → merge to master
```

## Data Sources (v2 Enhancements)

v2 adds improvements to data pipeline:
- **SEC EDGAR Client**: Full integration for prospectus parsing
- **BLS Caching**: 24-hour TTL with disk persistence
- **Census/Zillow Ready**: Configured, awaiting API keys
- **Loan Deduplication**: Match SEC to Freddie Mac loans

## Testing

Run full test suite:
```bash
cd calibration
pytest tests/ -v --cov=calibration --cov-report=html
```

Run praxis-gate (before commit):
```bash
bash /workspace/.swarm/praxis/toolkit/bin/praxis-gate.sh
```

## Support
- Issues/PRs: [private-repo]
- Documentation: See `/calibration/docs/`
- Architecture: See `DEPLOYMENT.md` and feature specs

---
Built with ForwardAI praxis build doctrine
