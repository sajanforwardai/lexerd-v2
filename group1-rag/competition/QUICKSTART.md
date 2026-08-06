# QUICKSTART: Multi-Agent Strategy Competition

Get started in 15 minutes. This guide covers basic setup, running your first competition, and building a custom agent.

## 5-Minute Setup

### Install Dependencies

```bash
cd /workspace/group1-rag
pip install numpy pandas pytest  # Already installed in most environments
```

### Initialize Components

```python
from competition.agent_pool import AgentPool
from competition.competition_engine import CompetitionEngine
from competition.regime_detector import RegimeDetector
from competition.strategy_agent import GreeksSnapshot, MarketState

# Create pool (6 default agents)
pool = AgentPool()

# Initialize competition
engine = CompetitionEngine(pool)

# Initialize regime detector
detector = RegimeDetector(use_kg=False)  # Set True if KG available

print("✓ Initialized competition framework")
print(f"  - {len(pool.agents)} agents ready")
print(f"  - Regimes: {detector.regime_history}")
```

## 10-Minute Competition Run

### Single Decision

```python
# Market snapshot
greeks = GreeksSnapshot(
    delta=0.35,
    gamma=0.15,
    theta=-0.01,
    vega=0.20,
    rho=0.05,
    vol_of_vol=0.12
)

market_state = MarketState(
    volatility=0.15,
    volatility_term_structure={"1m": 0.14, "3m": 0.16, "1y": 0.18},
    skew=0.05,
    term_structure_slope=0.04,
    events=[],
    regime="",
    price_momentum=0.3,
    correlation_regime="normal",
    liquidity_score=0.85
)

# Detect regime
regime, regime_confidence = detector.detect_regime(
    volatility=0.15,
    skew=0.05,
    term_structure_slope=0.04,
    price_momentum=0.3,
    vol_of_vol=0.12,
    events=[],
    correlation_regime="normal"
)

print(f"Detected regime: {regime} ({regime_confidence:.1%} confidence)")

# Get all agent selections
selections = pool.select_actions(regime, greeks, market_state)

print("\nAgent Selections:")
for agent_name, selection in selections.items():
    print(f"  {agent_name}: {selection.action_type.value} @ {selection.confidence:.1%}")

# Select winner
winner, hedge, reason = engine.get_winner_and_hedge(
    regime, selections, confidence_threshold=0.60
)

if winner:
    print(f"\n✓ Winner: {winner[0]}")
    print(f"  Strategy: {winner[1].strategy_name}")
    print(f"  Confidence: {winner[1].confidence:.1%}")
    print(f"  Exposure: {winner[1].target_exposure:.1f}")
    print(f"  Rationale: {winner[1].rationale}")
else:
    print(f"\n✗ Escalation: {reason}")
```

### Daily Loop (30 Days)

```python
import random
from datetime import datetime, timedelta

# Simulate 30 days of trading
daily_pnls = []

for day in range(1, 31):
    # Simulate market evolution
    vol = 0.10 + random.gauss(0, 0.05)
    momentum = random.gauss(0.2, 0.3)
    
    # Market snapshot
    greeks = GreeksSnapshot(
        delta=0.3 + momentum,
        gamma=0.15 - vol * 0.3,
        theta=-0.01,
        vega=vol,
        rho=0.05,
        vol_of_vol=0.12
    )
    
    market_state = MarketState(
        volatility=max(0.05, vol),
        volatility_term_structure={},
        skew=-0.1 if momentum < 0 else 0.1,
        term_structure_slope=0.04,
        events=[],
        regime="",
        price_momentum=momentum,
        correlation_regime="normal",
        liquidity_score=0.85
    )
    
    # Detect and select
    regime, _ = detector.detect_regime(
        volatility=max(0.05, vol), skew=market_state.skew,
        term_structure_slope=0.04, price_momentum=momentum,
        vol_of_vol=0.12, events=[], correlation_regime="normal"
    )
    market_state.regime = regime
    
    selections = pool.select_actions(regime, greeks, market_state)
    winner, hedge, reason = engine.get_winner_and_hedge(regime, selections)
    
    # Simulate trade outcome
    if winner:
        pnl = random.gauss(50, 30)
        engine.update_elo_from_trade(winner[0], regime, pnl)
        daily_pnls.append(pnl)
    else:
        daily_pnls.append(0)

print(f"\n30-Day Results:")
print(f"  Total P&L: {sum(daily_pnls):.1f}")
print(f"  Win Rate: {sum(1 for p in daily_pnls if p > 0) / len(daily_pnls):.1%}")
print(f"  Avg Daily: {sum(daily_pnls) / len(daily_pnls):.1f}")
```

## Build Your First Agent (5 Minutes)

### Simple Custom Agent

```python
from competition.strategy_agent import (
    StrategyAgent, ActionType, GreeksSnapshot, MarketState, StrategySelection
)

class SimpleVegaAgent(StrategyAgent):
    """Simple agent that trades on vega signals."""
    
    def __init__(self):
        super().__init__("SimpleVegaAgent")
        self.optimized_regimes = ["bull_high_vol", "bear_high_vol"]
    
    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        # Simple signal: high vega and vol → go long
        vega_signal = min(greeks.vega / 0.5, 1.0)
        vol_signal = min(market_state.volatility / 0.4, 1.0)
        
        combined_confidence = (vega_signal * 0.6) + (vol_signal * 0.4)
        
        if combined_confidence > 0.7:
            action = ActionType.LONG
            exposure = 0.7
        elif combined_confidence > 0.5:
            action = ActionType.HEDGE
            exposure = 0.3
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0
        
        return StrategySelection(
            strategy_name="simple_vega",
            action_type=action,
            confidence=combined_confidence,
            rationale=f"Vega={vega_signal:.2f}, Vol={vol_signal:.2f}",
            target_exposure=exposure
        )
    
    def get_description(self) -> str:
        return "Simple vega-based agent for high-vol regimes"

# Add to pool
pool.add_agent(SimpleVegaAgent())
print(f"✓ Added custom agent (pool now has {len(pool.agents)} agents)")

# Use immediately
selections = pool.select_actions("bull_high_vol", greeks, market_state)
print(f"  SimpleVegaAgent selection: {selections['SimpleVegaAgent'].action_type.value}")
```

### Intermediate Custom Agent (With Learning)

```python
from statistics import mean

class ImprovedSkewAgent(StrategyAgent):
    """Agent that improves via learning."""
    
    def __init__(self):
        super().__init__("ImprovedSkewAgent")
        self.optimized_regimes = ["bear_high_vol", "stress"]
        self.recent_trades = []  # Track recent performance
    
    def select_action(
        self,
        regime: str,
        greeks: GreeksSnapshot,
        market_state: MarketState
    ) -> StrategySelection:
        # Base regime confidence
        regime_confidence = 0.85 if regime in self.optimized_regimes else 0.5
        
        # Skew extremeness
        skew_extremeness = abs(market_state.skew)
        skew_confidence = 0.9 if skew_extremeness > 0.7 else 0.4
        
        # Vol support (vol-of-vol declining → fade)
        vol_support = 1.0 - min(greeks.vol_of_vol / 0.4, 1.0)
        vol_confidence = 0.7 if vol_support > 0.5 else 0.3
        
        # Adaptive confidence based on recent performance
        adaptive_boost = self._calculate_performance_boost()
        
        combined_confidence = (
            regime_confidence * 0.3 +
            skew_confidence * 0.4 +
            vol_confidence * 0.3
        ) * (1.0 + adaptive_boost)
        
        combined_confidence = min(combined_confidence, 1.0)
        
        if combined_confidence > 0.75:
            action = ActionType.SHORT  # Fade the extreme
            exposure = 0.7
        elif combined_confidence > 0.5:
            action = ActionType.HEDGE
            exposure = 0.3
        else:
            action = ActionType.NEUTRAL
            exposure = 0.0
        
        return StrategySelection(
            strategy_name="improved_skew",
            action_type=action,
            confidence=combined_confidence,
            rationale=f"Skew={market_state.skew:.2f}, Vol-of-vol={greeks.vol_of_vol:.2f}",
            target_exposure=exposure,
            metadata={
                "skew_extremeness": float(skew_extremeness),
                "performance_boost": float(adaptive_boost)
            }
        )
    
    def _calculate_performance_boost(self) -> float:
        """Boost confidence if recent trades are profitable."""
        if not self.recent_trades:
            return 0.0
        
        recent_wins = sum(1 for trade in self.recent_trades[-10:] if trade > 0)
        win_rate = recent_wins / min(len(self.recent_trades[-10:]), 10)
        
        return (win_rate - 0.5) * 0.2  # Boost if win_rate > 50%
    
    def record_trade_outcome(self, pnl: float):
        """Record trade outcome for learning."""
        self.recent_trades.append(pnl)
        if len(self.recent_trades) > 50:  # Keep last 50
            self.recent_trades.pop(0)
    
    def get_description(self) -> str:
        return "Adaptive skew fading agent with performance learning"

pool.add_agent(ImprovedSkewAgent())
```

## Run Tests

### Quick Smoke Test

```bash
cd /workspace/group1-rag/competition
python -m pytest test_competition.py::TestStrategyAgent -v
```

### Full Test Suite

```bash
python -m pytest test_competition.py -v --tb=short
```

### Performance Test (Latency)

```python
import time

# Warmup
for _ in range(3):
    pool.select_actions("bull_low_vol", greeks, market_state)

# Measure
start = time.time()
for _ in range(100):
    pool.select_actions("bull_low_vol", greeks, market_state)
elapsed = (time.time() - start) * 1000 / 100

print(f"Average selection latency: {elapsed:.2f}ms (target: <50ms)")
```

## Run Full Example

```bash
python example_competition.py
```

Output:
```
2026-08-06 10:30:45 - root - INFO - Starting example competition...
2026-08-06 10:30:45 - root - INFO - Initialized DailyCompetition
2026-08-06 10:30:45 - root - INFO - Starting 30-day competition
2026-08-06 10:30:46 - root - INFO - Day 1: regime=bull_low_vol (85%), winner=GammaScalpingAgent, pnl=45.2
...
=== FINAL REPORT ===
Total P&L: 1,245.60
Win Rate: 62.3%
Sharpe Ratio: 1.45
Max Drawdown: 125.00

=== FINAL RANKINGS ===
bull_low_vol:
  1. GammaScalpingAgent: Elo=1680, Games=8, WR=75%
  2. MomentumAgent: Elo=1620, Games=8, WR=62%
```

## Common Patterns

### Integration with ObservationCollector

```python
from learning import ObservationCollector

collector = ObservationCollector()

# After trade execution, record it
collector.record_trade(
    trade_id="trade_001",
    strategy="gamma_scalping",
    instrument="BTC/USD",
    side="buy",
    quantity=1.0,
    entry_price=100.0,
    exit_price=105.0,
    pnl=5.0,
    greeks={"delta": 0.3, "gamma": 0.15, ...},
    regime_at_entry="bull_low_vol"
)

# Daily learning update
trades = collector.get_trades_by_strategy("gamma_scalping")
for trade in trades:
    if trade.pnl:
        engine.update_elo_from_trade(
            "GammaScalpingAgent",
            trade.regime_at_entry,
            pnl=trade.pnl
        )
```

### Export and Monitoring

```python
# Export competition state
engine.export_state("competition_state.json")

# Export regime history
detector.export_regime_history("regime_history.json")

# Get current rankings
rankings = engine.get_global_rankings()
for regime, agents in rankings.items():
    print(f"\n{regime}:")
    for agent in agents[:3]:
        print(f"  {agent['agent_name']}: Elo={agent['rating']:.0f}")

# Get competition statistics
stats = engine.get_competition_stats()
print(f"Total games: {stats['total_games_played']}")
print(f"Overall win rate: {stats['overall_win_rate']:.1%}")
```

### Regime Monitoring

```python
# Get current regime strength
strength = detector.get_regime_strength()
print(f"Current regime confidence: {strength['current_regime_confidence']:.1%}")
print(f"Regime stability: {strength['regime_stability']:.1%}")

# Get regime history
history = detector.get_regime_history(last_n=10)
for entry in history:
    print(f"  {entry['timestamp']}: {entry['regime']} ({entry['confidence']:.1%})")
```

## Debugging

### Agent Not Making Selections

```python
# Check agent directly
agent = pool.get_agent_by_name("GammaScalpingAgent")
selection = agent.select_action("bull_low_vol", greeks, market_state)

if selection.action_type.value == "neutral":
    print("Agent returned neutral - check:")
    print(f"  - Regime match: {selection.confidence:.2%}")
    print(f"  - Rationale: {selection.rationale}")
```

### Low Confidence Always

```python
# Check regime detection
regime, conf = detector.detect_regime(...)
print(f"Regime detected: {regime} (confidence: {conf:.1%})")

# If confidence low, verify inputs are in valid ranges
print(f"  vol: {vol} (should be 0-1)")
print(f"  skew: {skew} (should be -1 to 1)")
print(f"  momentum: {momentum} (should be -1 to 1)")
```

### Elo Not Converging

```python
# Check Elo ratings
rankings = engine.get_regime_rankings("bull_low_vol")
for agent in rankings:
    print(f"{agent['agent_name']}: {agent['rating']:.0f} (K={agent.get('k_factor', 32)})")

# If all equal, agents haven't played enough games yet
# If diverging, the K-factor may be too high (increase if <20 games)
```

## Next Steps

1. **Read Full Docs**: See [README.md](README.md) for complete API reference
2. **Build Custom Agents**: Extend `StrategyAgent` with your strategies
3. **Integrate Learning**: Hook up `ObservationCollector` for real feedback
4. **Monitor Daily**: Track Elo ratings and regime leaders
5. **Deploy**: Integrate into live trading system

## API Quick Reference

```python
# Initialization
pool = AgentPool()                           # Create default pool
engine = CompetitionEngine(pool)             # Competition manager
detector = RegimeDetector(use_kg=False)      # Regime classifier

# Decision Making
regime, conf = detector.detect_regime(...)   # Detect regime
selections = pool.select_actions(...)        # Get all agent selections
winner, hedge, reason = engine.get_winner_and_hedge(...)  # Select winner

# Learning
engine.update_elo_from_trade(agent, regime, pnl)  # Update after trade

# Monitoring
rankings = engine.get_global_rankings()      # Get agent rankings
stats = engine.get_competition_stats()       # Competition metrics
engine.export_state(filepath)                # Save state
```

## Support

- **Full Documentation**: [README.md](README.md)
- **Example Code**: [example_competition.py](example_competition.py)
- **Tests**: [test_competition.py](test_competition.py)
- **Issues**: Check error logs and validation in agent.select_action()
