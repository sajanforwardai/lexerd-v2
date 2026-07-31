# Lexerd Deal Engine v2

Next-generation multifamily acquisition scoring and opportunity identification platform.

## Features

- **Unified Multifamily Sourcing**: GSE (Freddie Mac/Fannie Mae) + Private-Label CMBS coverage
- **3M Model Scoring**: Market (30%) + Model (40%) + Management (30%)
- **Real-Time Opportunity Pipeline**: Maturity-based ranking with refinance pressure signals
- **Professional Dashboard**: Streamlit-based web interface with responsive design

## Project Structure

```
lexerd2/
├── calibration/          # Core scoring engine
│   ├── models/          # Thesis, scoring logic
│   ├── data/            # Data clients (BLS, SEC, etc.)
│   ├── opportunities/   # Loan loading & ranking
│   ├── ui/              # Streamlit dashboard
│   └── tests/           # Test suite
├── site/                # Static deployment files
└── docs/                # Documentation
```

## Development

```bash
cd calibration
streamlit run ui/app.py --server.port 8505
```

## Deployment

Deployed at: https://forwardai.dev/sg-lexerdcapitalmanagement-v2 (configure as needed)

---

Built with the ForwardAI system + Praxis build doctrine
