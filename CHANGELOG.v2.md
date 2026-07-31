# Lexerd Deal Engine v2 Changelog

## v2.0.0 - Initial Release (2026-07-31)

### New Features
- **Separate v2 Codebase**: Full copy of v1 with independent deployment path
- **Port 8506 Deployment**: Runs alongside v1 (port 8505) for A/B testing
- **Enhanced Data Pipeline**: Full SEC EDGAR integration, BLS caching, Census/Zillow ready
- **Professional Dashboard**: Streamlit with SaaS design patterns
- **Comprehensive Testing**: 100+ unit tests, praxis-gate compliance

### Data Sources
- Freddie Mac Multifamily Loan Database (B3 tapes)
- SEC CMBS Filings (424B5 prospectuses, 10-D servicer reports)
- BLS Employment Data (20+ MSA codes)
- Census Population & Zillow Multifamily (configured, ready for integration)

### Architecture
- Modular calibration package (models, data, opportunities, pipeline)
- Parallel worktree support for feature development
- Full test coverage with pytest + praxis-gate
- Production-ready configuration

### Deployment
- Streamlit on port 8506
- Nginx reverse proxy to `/sg-lexerdcapitalmanagement-v2`
- Static site deployment via `/workspace/site/`
- GitHub repo: [private-repo-url-here]

---

## Migration from v1
See `MIGRATION-GUIDE.md` for upgrading from v1 to v2
