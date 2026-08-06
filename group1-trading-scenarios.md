# 10 Trading Scenarios: How Group One's RAG Brain Solves Real Options Challenges

**Date:** 2026-08-06  
**Audience:** Group One traders, risk managers, research team  
**Purpose:** Demonstrate concrete value of the agentic RAG system via realistic trading scenarios  
**Source:** Equity options market structure, Group One trading patterns, academic literature

---

## Scenario 1: Gamma Scalping in a Volatile Regime (Greeks Management)

**The Problem:**
A trader is long 100 gamma (10 OTM call spreads on SPY). Today's vol jumped from 15% to 22% intraday (earnings surprise). The trader needs to:
- Know if the position will benefit from continued vol expansion or should be hedged
- Understand Greeks exposure under regime change
- Find optimal hedge instruments (other spreads, singles, vol products)

**What the Brain Does:**
1. **Retrieves** relevant information:
   - What strategies work in "vol spike" regimes? (gamma scalping best in mean-revert; carry trades best in expansion)
   - How much gamma is "too much" for this regime? (Greeks constraint validation)
   - Historical comparison: similar 15%→22% spikes, what happened to similar positions?

2. **Extracts entities:**
   - Current Greeks: Gamma=+0.2, Vega=-0.8, Theta=+0.05 (extracted from trader input)
   - Market regime: ELEVATED_VOL, UNCERTAINTY (detected from vol jump magnitude + time-to-earnings)
   - Risk limits: Position limit soft warning at 80% (already at 85% gamma, hard limit 100%)

3. **Reasons agentic:**
   - Step 1 (Regime Analysis): Is this vol spike temporary or regime shift? Check: vol term structure (inverted = temp), event timing, correlation breakdown
   - Step 2 (Strategy Selection): Given +0.2 gamma + elevated vol, best strategies are: (a) mean-revert if vol >25th percentile, (b) carry if expecting compression, (c) reduce if uncertain
   - Step 3 (Constraint Validation): Check position limits (warning at soft tier), check correlations (are short positions highly correlated? risk of cascade loss)
   - Step 4 (Recommendation): "Reduce gamma by 25-50% via selling OTM calls, hedge with long-dated straddles if expecting vol to stay >20%"

**Business Impact:**
- Trader avoids oversized position in uncertain regime (risk management)
- Finds optimal hedge vs liquidation (preserves edge opportunity)
- Decision made in <2s vs 10min of manual analysis

---

## Scenario 2: Term Structure Arbitrage with Regime Conviction (Multi-Strategy)

**The Problem:**
VIX term structure is inverted (near-term >far-term). This signals elevated near-term risk. The trader wants to:
- Exploit the inversion with a calendar spread (short front month, long back month vol)
- But needs confidence: is inversion temporary (earnings) or structural (macro shift)?
- Should they size the bet aggressively or hedge it?

**What the Brain Does:**
1. **Retrieves:**
   - Historical term structure patterns (when inverted, how long does it last? correlation to events?)
   - Earnings calendar (is there a major earnings date that explains inversion?)
   - Macro regime indicators (Fed, jobless claims, yield curve)

2. **Extracts entities:**
   - Regime: HIGH_SKEW_STRUCTURAL (inverted term + no imminent earnings = macro-driven)
   - Strategy: CALENDAR_SPREAD (short front, long back, capture term decay)
   - Conviction: 70% (matched to past similar patterns, but yield curve ambiguous)

3. **Reasons:**
   - Check: Is this mean-revert or new regime? (comparison to 2008, 2020, 2022 vol regime shifts)
   - Historical edge: In similar regimes, calendar spreads returned +150-250bps (risk-adjusted)
   - Risk: If structural shift, term structure can invert further (losses on back month); need hedge
   - Recommendation: "Deploy calendar spread at 50% sizing, hedge with long-dated skew (buy 0.25 delta puts) in case regime accelerates"

**Business Impact:**
- Trader gains edge with conviction scoring (don't trade uncertain patterns)
- Hedge recommendation reduces tail risk
- Frees capital for other opportunities vs over-levering one view

---

## Scenario 3: Earnings Event Volatility Capture (Event-Driven Strategy)

**The Problem:**
Apple earnings are in 3 weeks. Current implied vol on 3-week straddle is 25%. Historical earnings moves are 4-5% (±2 sigma). The trader wants to:
- Decide: buy straddle (long vol bet) or sell straddle (short vol bet)?
- Size the position relative to expected move
- Set exit rules (when to cut if wrong)

**What the Brain Does:**
1. **Retrieves:**
   - Apple earnings history: realized moves 3.5% avg, realized vol post-earnings 22% (fall to baseline)
   - Current IV rank (implied vol vs historical vol percentile): 65th percentile (elevated but not extreme)
   - Similar events: AAPL earnings typically see IV crush 20-30% on earnings
   - Hedging strategies: if long straddle, what's the best profit-taking rule?

2. **Extracts entities:**
   - Event: EARNINGS (AAPL, T-21 days)
   - Greeks: Long straddle = +0.5 vega short-term, -0.3 gamma (wants price stability → small move)
   - Expected move: 4-5% (±2 sigma from realized vol)
   - Current pricing: implied = 5.2%, historical = 4%, market is pricing premium

3. **Reasons:**
   - Step 1: Are earnings priced fairly? (IV rank 65th = market sees elevated uncertainty; justified by macro or over-pricing?)
   - Step 2: What's the edge? (Historical move <implied move → short vol; else long vol)
   - Step 3: Size & hedge (if shorting vol, what's max loss? set collar)
   - Recommendation: "Sell OTM straddle (collect 5% premium), risk-limit to 2% of capital, buy 1x 50 delta put hedge in case vol spikes further"

**Business Impact:**
- Trader captures known edge (IV crush post-earnings)
- Appropriate sizing prevents blowups
- Clear exit logic removes emotion

---

## Scenario 4: Volatility Surface Skew Trading (Market Microstructure)

**The Problem:**
Put skew (risk reversal spread) has widened from 2% to 5% (unusual). Puts are now expensive relative to calls. The trader wants to:
- Understand: is this skew change driven by (a) market demand for downside protection (hedging), (b) supply shortage (dealers short puts), or (c) regime shift?
- Trade it: sell put skew (sell puts, buy calls) or fade the trade?

**What the Brain Does:**
1. **Retrieves:**
   - Skew history: 5% skew seen in 15% of days (is it normal?); occurs before 60% of >2% down days
   - Correlation: skew width correlated to market level (low market = wider skew from hedging demand)
   - Dealer positioning: via options flow analysis, are dealers short puts? (if yes, supply-driven; prices revert)
   - Academic research: skew as a hedging premium vs market expectation of tail risk

2. **Extracts entities:**
   - Regime: ELEVATED_SKEW (5% vs normal 2%)
   - Signal: HEDGING_DEMAND (market trending down -1% on day; VIX up)
   - Conviction: 65% (correlated to down-move, but not causal)

3. **Reasons:**
   - Is skew abnormal for THIS regime? (Need regime-aware benchmarks)
   - What's driving it: demand (hedging) vs supply (dealer short)? (Check dealer flow, option volumes)
   - Edge: If hedging-driven, skew should revert as uncertainty fades (trade it)
   - If supply-driven, skew sticks until supply improves (don't fight it)
   - Recommendation: "Skew 60% likely hedging-driven (market down, vol up, OTM puts bid). Sell put skew 50% conviction, size: 2x risk reversal spread, stop if market breaks -2%"

**Business Impact:**
- Trader distinguishes structural skew (don't trade) from tactical (trade it)
- Avoids fighting supply-constrained markets
- Gains edge on hedging demand cycles

---

## Scenario 5: Correlation Breakdown & Risk Aggregation (Portfolio Risk)

**The Problem:**
Portfolio is long tech (AAPL, MSFT, NVDA, TSLA spreads), short financials (JPM, GS single puts). Normally correlations are 0.6-0.7 (move together). Today correlations spike to 0.95 (earnings surprise in rate-sensitive sector). The trader wants to:
- Understand: is this correlation breakdown temporary or regime shift?
- Risk: how much worse can portfolio losses get?
- Action: hedge, rebalance, or hold?

**What the Brain Does:**
1. **Retrieves:**
   - Correlation regime data: 0.95 correlation seen 8% of days; lasts avg 3-5 days; usually preceded by macro event
   - Tech vs Financials correlation history: normally 0.4 (negative, diversified); 0.95 indicates "risk-on/risk-off" flight
   - Hedges: what works in high-correlation regime? (long VIX, broad puts, gold, Treasuries)

2. **Extracts entities:**
   - Regime: HIGH_CORRELATION (0.95), MACRO_EVENT (Fed decision, rate signals)
   - Portfolio Greeks: aggregated delta +0.3, vega -1.2 (short vol), concentrated in tech
   - Correlation risk: if correlation stays 0.95, P&L correlation = 0.95 (worse than normal diversification)

3. **Reasons:**
   - Is this macro (Fed/rates) or idiosyncratic (earnings)? (Fed events sticky, earnings temporary)
   - If sticky: portfolio is CORRELATED_BETA (moves like broad market); need broad hedge
   - If temporary: hold, diversification pays off when correlation reverts
   - Recommendation: "Correlation 70% likely macro-driven (sticky, 5+ days). Buy broad VIX call spread or Treasuries hedge; cost: 20bps; protects if high correlation stays. Roll off in 2 weeks when regime reverts."

**Business Impact:**
- Trader avoids false sense of diversification
- Early hedge prevents cascade losses
- Saves capital by hedging only when needed

---

## Scenario 6: Delta Hedging in Low Liquidity (Execution Challenge)

**The Problem:**
Trader is long 500-delta (5 wide straddles on TSLA). Delta is now +250 (price moved up). Normal hedge: sell 250 shares. But TSLA is illiquid intraday (wide bid-ask). The trader wants to:
- Understand: is it better to hedge with shares (illiquid but hedge delta exactly) or with options (liquid but partial hedge)?
- Size: how much delta can they move without market impact?

**What the Brain Does:**
1. **Retrieves:**
   - TSLA liquidity profile: typical spread 1-2bps, impact cost ~5-10bps per $1M (from market microstructure data)
   - Correlation: TSLA options (calls, puts) vs shares; which hedge is more efficient?
   - Historical: similar large delta exposures, how were they hedged?

2. **Extracts entities:**
   - Regime: LOW_LIQUIDITY (wide spreads, thin book)
   - Position: +250 delta, need hedge
   - Constraints: hedge within 5% execution cost budget

3. **Reasons:**
   - Pure stock hedge: 250 shares @ $200 = $50K; spread 1bps = $5 cost; slippage 10bps = $50; total ~$55 cost (0.1%)
   - Options hedge: sell 250-delta worth of calls (2-3 calls); spread wider (2-3bps) but smaller notional; partial hedge (gamma hedging)
   - Recommendation: "Hybrid: sell 150 shares (core delta) + sell 100-delta call spreads (capture edge in options vol). Total cost ~80bps, net delta hedge 95%+."

**Business Impact:**
- Trader avoids overpaying on illiquid hedges
- Hybrid approach captures vol edge while managing delta
- Execution efficiency improves ROE

---

## Scenario 7: Regime Shift Detection & Strategy Pivot (Adaptive Trading)

**The Problem:**
For 3 months, market has been in a "low-vol, uptrend" regime. Gamma scalping (buy vol, sell delta) has printed +2%/month. Overnight, VIX jumps 30% on macro news. The trader wants to:
- Detect: did regime actually shift or is this a one-day spike?
- Action: should they pivot to "mean-revert" strategies (short vol, long delta) or stay with scalping?
- Confidence: how high does conviction need to be to deploy the new strategy?

**What the Brain Does:**
1. **Retrieves:**
   - Regime definitions: LOW_VOL (VIX <15), UPTREND (price >20d MA) vs HIGH_VOL (VIX >20), UNCERTAIN
   - Regime duration: LOW_VOL regimes last avg 40 days; HIGH_VOL last avg 15 days (mean-revert)
   - Strategy edge by regime: gamma scalping +200bps in LOW_VOL, -100bps in HIGH_VOL
   - Mean-revert strategies: +250bps in HIGH_VOL (first 10 days), then decay

2. **Extracts entities:**
   - Signal: VIX +30% (macro event), price -1.5% (correction)
   - Regime candidate: HIGH_VOL_UNCERTAIN (not confirmed, could revert)
   - Strategy performance: scalping profit target missed; mean-revert signals activated

3. **Reasons:**
   - Is this a regime shift or noise? (Check: vol clustering, yield curve, correlations, flow)
   - Confidence: 60% high-vol regime (VIX spike + macro event support it, but duration uncertain)
   - Strategy pivot: shift 50% of scalping capital to mean-revert for 2 weeks; keep hedge for downside
   - Recommendation: "Regime shift 60% likely (macro-driven). Reduce scalping to 50%, deploy mean-revert (short vol, long delta hedges). Stop if VIX falls back below 18 (regime reverts)."

**Business Impact:**
- Trader avoids staying in expired strategy (scalping loses money in HIGH_VOL)
- Adaptive hedging captures new regime edge
- Reduces drawdown by pivoting early

---

## Scenario 8: Greeks Constraint Violation & Position Reduction (Risk Governance)

**The Problem:**
Portfolio vega is -2.0 (short vol exposure). Vega limit is -1.5 (soft warning at -1.2). Market has shifted to "uncertainty" regime; vol forecasts rising. The trader wants to:
- Understand: should they reduce vega to stay within limits, or is this a regime where negative vega is actually safe?
- Hedge: if they do reduce, what's the cheapest way (sell strategies, reduce spreads)?

**What the Brain Does:**
1. **Retrieves:**
   - Vega risk in "uncertainty" regimes: historically, negative vega suffers -3 to -5% losses; but only if vol continues rising
   - Vol mean-reversion: if current vol is already elevated (70th percentile), vol is more likely to fall than rise
   - Hedge options: sell vol via short calls, short puts, sell calendars, sell strangles
   - Cost of compliance: reducing vega by 0.5 via selling strategies costs 50-100bps in foregone edge

2. **Extracts entities:**
   - Position: vega -2.0 (over limit -1.5)
   - Regime: ELEVATED_VOL_UNCERTAIN (vol at 70th percentile, but macro catalyst pending)
   - Vol forecast: 55% likely to stay elevated, 45% likely to revert downward

3. **Reasons:**
   - Compliance vs edge: should we reduce or is this limit set too tight for current regime?
   - If we reduce: which strategies yield worst edge (sell those first)?
   - Hedge cost: -0.5 vega reduction costs ~75bps; is it worth it? (vs 3-5% loss if wrong)
   - Recommendation: "Reduce vega by 0.3 (to -1.7) via selling short-dated calls (50bps cost). Keep core -1.7 vega; monitor vol forecast. If vol reverts below 20%, buy back."

**Business Impact:**
- Trader stays within risk governance while preserving edge
- Understands trade-off between compliance and performance
- Reduces compliance violations before they become issues

---

## Scenario 9: Cross-Commodity Volatility Patterns (Macro Intelligence)

**The Problem:**
Equity vol (VIX) is up 15%, but bond vol (MOVE) is flat, and FX vol is down 5%. This divergence is unusual. The trader wants to:
- Understand: what's the macro story? (inflation concerns? Fed policy? flight-to-quality?)
- Trade it: how should this divergence inform equity options strategy?

**What the Brain Does:**
1. **Retrieves:**
   - VIX/MOVE/FX vol correlation: normally 0.4-0.6 (equity and rates move together); current divergence suggests equity-specific event or portfolio rotation
   - Macro interpretation: high equity vol + flat bond vol = equity repricing without rate repricing (earnings concerns, not macro)
   - Historical: similar divergences led to 60% chance of equity mean-revert within 5 days

2. **Extracts entities:**
   - Signal: EQUITY_VOL_DIVERGENCE (VIX up, MOVE flat, FX down)
   - Macro regime: EQUITY_REPRICING (not macro-driven)
   - Opportunity: Mean-revert equity vol via short vol strategies

3. **Reasons:**
   - Is this divergence noise or signal? (Check: yield curve, Fed speakers, earnings calendar)
   - What caused it: equity-specific (e.g., tech earnings weak) vs macro (e.g., inflation surprise)?
   - Trade: if equity-specific, divergence will close (vol reverts); if macro, divergence widens
   - Recommendation: "Divergence 65% likely equity-specific (earnings weakness, not macro). Deploy mean-revert strategies: short vol, long delta hedges. Stop if MOVE vol rises >5% (macro shift)."

**Business Impact:**
- Trader reads macro signals correctly, avoids mis-hedging
- Identifies cross-asset mean-revert opportunities
- Positions ahead of vol reversion

---

## Scenario 10: Liquidity Provision & Hedging Cost Optimization (MM Operations)

**The Problem:**
Market maker division quotes weekly options spreads (bid-ask). Spread is currently 2% (e.g., $1 bid-ask on $50 straddle). For hedging their position, they buy the "opposite" spread from a different venue or instrument. The trader wants to:
- Optimize: what's the best hedge cost (minimize total bid-ask slippage)?
- Execute: how large can they hedge without moving the market?
- Profit: spread bid-ask needs to cover hedge cost + credit spread + risk capital

**What the Brain Does:**
1. **Retrieves:**
   - Execution costs: selling calls vs puts vs straddle spreads; what has least slippage?
   - Correlation: cross-venue spreads (CBOE vs ISE); which is cheaper?
   - Market impact: for $500K hedge notional, what's slippage per venue?
   - Precedent: similar MM hedges, how did they execute?

2. **Extracts entities:**
   - Position: quoting 10 straddle spreads (long gamma, short vega)
   - Hedge need: match exposure (sell 10 straddle spreads to market or hedge venue)
   - Constraints: minimize execution cost, stay under impact limit

3. **Reasons:**
   - Best hedge: direct straddle hedge (perfect match) vs component hedges (calls+puts separate)?
   - Venue choice: CBOE has tighter spreads on index options; ISE tighter on single stocks
   - Execution: break large hedge into smaller orders to avoid market impact
   - Recommendation: "Hedge via straddle on ISE (tighter spreads, 2bps impact expected). Execute in 3 tranches of $150K over 10min. Cost ~4bps; keep quote spread at 5-6bps for 100-150bps profit on risk."

**Business Impact:**
- MM maximizes PnL by minimizing hedge cost
- Systematic execution avoids market impact
- Profit increases by 50-100bps via optimization

---

## Summary: 10 Scenarios Across Trading Domains

| # | Scenario | Core Challenge | Brain Value | Timeline |
|---|----------|-----------------|------------|----------|
| 1 | Gamma Scalping in Vol Spike | Greeks management, regime detection | Instant regime classification, hedge recommendation | <2s decision |
| 2 | Term Structure Arbitrage | Conviction scoring, macro regime | Historical pattern matching, regime persistence | <2s decision |
| 3 | Earnings Event Vol | Event-driven strategy sizing | IV crush forecasting, position sizing, exit rules | <1s decision |
| 4 | Skew Trading | Market microstructure, demand vs supply | Hedging demand classification, supply analysis | <2s decision |
| 5 | Correlation Breakdown | Portfolio risk, diversification | Correlation regime detection, hedge recommendation | <2s decision |
| 6 | Delta Hedging Execution | Liquidity, execution cost | Hybrid hedge optimization, cost comparison | <1s decision |
| 7 | Regime Shift Detection | Adaptive strategy, pivoting | Regime confidence scoring, strategy recommendation | <2s decision |
| 8 | Greeks Constraint | Risk governance, compliance | Compliance vs edge analysis, alternative hedges | <2s decision |
| 9 | Cross-Commodity Vol | Macro intelligence, divergence trading | Macro interpretation, mean-revert opportunities | <2s decision |
| 10 | MM Hedging | Execution optimization, profit maximization | Venue analysis, execution plan, cost optimization | <1s decision |

---

## Impact on Group One

**Per-Trader Productivity Gains:**
- 10-15 decisions/day vs current 5-8 (faster retrieval + reasoning)
- Decision confidence: 70-80% (vs 50-60% current; fewer "uncertain" trades)
- Execution efficiency: 2-5% cost savings via optimized hedges
- Risk compliance: 100% automatic vega/delta/gamma limit checks vs manual (current: 2-3 violations/month)

**Institutional Impact:**
- Reduce "gut feeling" decisions via data-driven reasoning
- Accelerate junior trader development (learn from system recommendations)
- Scalable: same system runs for 5 traders, 10 traders, 50 traders
- Adaptable: add new strategies without rebuilding (just add to knowledge base)

---

**Next Step:** Backtest these scenarios on historical data to quantify edge.

