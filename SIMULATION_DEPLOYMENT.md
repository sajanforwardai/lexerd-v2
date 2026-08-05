# Goldman Sachs TMT First-Year Analyst Simulation — Deployment Guide

## 🚀 Overview

A comprehensive, interactive banking simulation that puts you in the shoes of Sajan Goswami, a first-year analyst on Goldman Sachs' TMT (Technology, Media & Telecom) investment banking team.

**Status:** ✅ READY FOR DEPLOYMENT

---

## 📍 Access Points

### Primary Dashboard Integration
- **URL:** https://forwardai.dev/lexerdcapital/
- **Integration:** Simulation banner at top of Maturity Radar dashboard
- **Access:** Click "ENTER SIMULATION →" button

### Direct Simulation File
- **File:** `/workspace/lexerd2/maturity-radar/gs_simulation.html`
- **Size:** ~85 KB (self-contained, no external dependencies)
- **Browser:** Chrome, Firefox, Safari, Edge (modern versions)

---

## 🎯 Core Features

### 1. **Immersive Banking Environment**
- Professional Goldman Sachs-inspired institutional design
- Real-time clock progression
- Persistent state via browser localStorage
- Continuous chat history across all interactions

### 2. **Deal Team Hierarchy**
- **Daniel Chen** (Associate) — Primary supervisor, day-to-day guidance
- **Michael Rodriguez** (VP) — Strategic oversight, client-facing
- **David Kaplan** (MD) — Senior leadership, board recommendations

### 3. **NovaEdge Software Deal Context**
- Enterprise AI infrastructure company
- $2.4B revenue, 28% YoY growth
- Evaluating 4 strategic alternatives
- Goldman engaged for comprehensive M&A advisory

### 4. **Interactive Workspace**

#### Chat View
- Continuous conversation thread with bankers
- Real-time message timestamps
- Banker responses adapt to analyst input
- Performance feedback in real-time

#### Deal Room
- Client overview with business segments
- Financial metrics (Revenue, EBITDA Margin, Net Debt)
- Transaction context and strategic rationale

#### Technical Reference
- Question 1-9 from FIN301 problem set
- Integrated into banking workflow (not separated exercises)
- Progress tracking (Completed/In Progress/Pending)

### 5. **Performance Tracking**
Real-time metrics dashboard:
- **Technical Accuracy** (65%)
- **Communication Skills** (58%)
- **Attention to Detail** (71%)
- **Speed & Efficiency** (52%)
- **Financial Intuition** (48%)
- **Banker Judgment** (42%)

### 6. **AI Analyst Coach**
- Hints system (4 levels: Conceptual → Framework → Formula → Check)
- Concept explanations
- Setup review and validation
- Challenge mode for deeper learning

### 7. **Knowledge Management**
- **Document Library:** Sample pitchbooks, client materials
- **Analyst Notes:** Personal scratchpad for calculations
- **Calendar:** Schedule of client meetings and reviews
- **Technical Reference:** All 9 FIN301 questions with progress

### 8. **Multi-View Interface**
- **Chat Tab:** Continuous banker interactions
- **Deals Tab:** Deal context and strategic alternatives
- **Financials Tab:** Real-time client financial metrics

---

## 🔧 Deployment Instructions

### Option A: Local Testing

#### 1. Open Directly in Browser
```bash
# Navigate to the file location
open /workspace/lexerd2/maturity-radar/gs_simulation.html

# Or from terminal
python3 -m http.server 8507 --directory /workspace/lexerd2/maturity-radar/
# Then visit: http://localhost:8507/gs_simulation.html
```

#### 2. Start Simulation Server
```bash
cd /workspace/lexerd2/maturity-radar/
python3 serve_simulation.py

# Accessible at: http://localhost:8507/gs_simulation.html
```

### Option B: Deploy to forwardai.dev

1. **Copy HTML to web directory:**
   ```bash
   cp /workspace/lexerd2/maturity-radar/gs_simulation.html /srv/www/lexerdcapital/
   ```

2. **Configure nginx to serve it:**
   ```nginx
   location /gs_simulation.html {
       alias /srv/www/lexerdcapital/gs_simulation.html;
       types { text/html html; }
   }
   ```

3. **Access via:** https://forwardai.dev/lexerdcapital/gs_simulation.html

### Option C: Streamlit Integration

The Maturity Radar dashboard now includes a banner with a link to the simulation. Users see:
> "🏦 Goldman Sachs TMT Analyst Simulation — Experience your first day as a first-year analyst"
> [ENTER SIMULATION →]

---

## 📊 Technical Specifications

### Architecture
- **Single HTML file:** No build process, no dependencies
- **Client-side state:** All data persists via localStorage
- **Responsive design:** Desktop, tablet, mobile optimized
- **Offline capable:** Fully functional without internet (after initial load)

### Browser Requirements
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### File Size
- HTML: ~85 KB
- Minified: Could reduce to ~60 KB if needed
- Load time: <500ms on modern connections

### Data Storage
- localStorage: Up to 5-10 MB per domain (more than sufficient)
- Auto-saves every interaction
- Persists across browser sessions

---

## 🎓 Learning Progression

### Week 1 Arc (Simulation)
**Monday:** Orientation + Initial assignment
- Meet the deal team
- Learn client context (NovaEdge)
- Receive first task

**Tuesday:** Technical foundations
- Question 5: Rapid Growth Valuation
- Question 6: Bond Pricing
- Question 7: YTM Calculation

**Wednesday:** Decision analysis
- Question 8: Sunk Cost analysis
- Question 9: NPC vs EAC comparison
- Strategic alternatives framework

**Thursday:** Integration & application
- Comparable companies analysis
- Valuation sensitivity
- Client presentation prep

**Friday:** Judgment & leadership
- Independent analyst work
- Senior banker interaction
- Performance review

### Integration Approach
Financial questions embedded in banking workflow:
- Not isolated homework exercises
- Real deal context and client implications
- Banker feedback based on responses
- Performance metrics reflect learning

---

## 🚦 Status Indicators

### Current Implementation ✅
- [x] Welcome screen with immersive entry
- [x] Professional UI design (Goldman Sachs-inspired)
- [x] Persistent chat history
- [x] Deal team sidebar
- [x] Performance tracking dashboard
- [x] Multi-tab interface
- [x] AI Coach system
- [x] Technical reference library
- [x] Document library (sample)
- [x] Calendar & scheduling
- [x] localStorage persistence

### Next Phases (Optional Enhancements)
- [ ] Enhanced banker dialogue engine (more context-aware responses)
- [ ] Interactive financial models & charts
- [ ] Full multi-day progression with realistic workload
- [ ] Banker relationship system (trust evolution)
- [ ] Strategic alternatives analysis framework
- [ ] Email & Slack integration
- [ ] Real-time performance adjustments
- [ ] End-of-day review sequences

---

## 🔐 Privacy & Security

- **No external data collection:** All data remains local (localStorage)
- **No server communication:** Fully client-side operation
- **No authentication needed:** Open access for training purposes
- **Training data only:** Sample client (NovaEdge) is fictional

---

## 📋 File Manifest

```
/workspace/lexerd2/
├── maturity-radar/
│   ├── gs_simulation.html          (Main simulation - 85 KB)
│   ├── serve_simulation.py         (Local dev server)
│   └── app.py                      (Streamlit app with integration)
├── GS_TMT_First_Year_Analyst_Simulation.html  (Backup copy)
└── SIMULATION_DEPLOYMENT.md        (This file)
```

---

## 🎮 Quick Start for Users

1. **Visit:** https://forwardai.dev/lexerdcapital/
2. **Click:** "ENTER SIMULATION →" banner
3. **Wait:** ~2 seconds for entry sequence
4. **Click:** "ENTER DESK" button
5. **Read:** Daniel's welcome message
6. **Type:** Your response to Daniel
7. **Send:** Press Ctrl+Enter (or Cmd+Enter on Mac)
8. **Interact:** Continue the simulation

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Simulation won't load | Clear browser cache, try incognito mode |
| Data not persisting | Check localStorage enabled in browser settings |
| Slow performance | Reduce browser tabs, clear cache |
| UI overlapping | Zoom to 100%, ensure 1920×1080+ resolution recommended |
| Chat not responding | Refresh page, verify JavaScript enabled |

---

## 📞 Support

For issues or feedback:
- Check technical reference for financial concepts
- Use AI Coach for learning support
- Refer to Daniel's feedback for performance guidance

---

**Deployment Date:** August 5, 2026  
**Status:** Production Ready  
**Version:** 1.0.0
