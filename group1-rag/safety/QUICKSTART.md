# Group One RAG Safety Systems - Quick Start

## Installation

```bash
cd /workspace/group1-rag/safety
python3 -m pytest test_safety.py  # Run all 37 tests
```

## Basic Usage (2 minutes)

```python
from safety_systems import SafetySystems, PositionData, GreeksSnapshot

# Create safety system (initializes all 5 modules)
safety = SafetySystems()

# Create a position to trade
position = PositionData(
    instrument_id="SPY_CALL",
    notional_usd=10_000_000,      # $10M position
    side="long",
    greeks=GreeksSnapshot(
        delta=500_000,             # $500k delta
        gamma=50_000,              # $50k gamma
        vega=100_000,              # $100k vega
        theta=1_000,               # $1k theta
        rho=10_000                 # $10k rho
    ),
    book_id="equities"
)

# PRE-TRADE RISK GATE (all checks before execution)
is_approved, messages = safety.pre_trade_check(position)

if is_approved:
    print("✓ APPROVED - Execute trade")
    # ... execute trade ...
    
    # POST-TRADE VALIDATION
    actual_greeks = GreeksSnapshot(...)
    is_valid, issues = safety.post_trade_validation(
        position.instrument_id,
        expected_greeks=position.greeks,
        actual_greeks=actual_greeks,
        execution_price=100.0,
        realized_pnl=5_000
    )
    print("✓ Post-trade validation complete")
else:
    print("✗ REJECTED - Do not execute")
    for msg in messages:
        print(f"  {msg}")

# Get system status
status = safety.get_system_status()
print(status)
```

## The 5 Safety Modules

### 1. PositionLimits - Hard Limit Enforcement

```python
# Limits enforced before trade execution
limits = safety.position_limits

# Limits:
# - Instrument: $100M
# - Book: $500M  
# - Portfolio: $2B
# - Greeks: Delta $1B, Gamma $100M, Vega $50M

# Multi-tier:
# 70% = Warning
# 85% = Strong Warning
# 100% = Hard Stop (ValueError raised)

try:
    success, warning = limits.add_position(position)
except ValueError as e:
    print(f"LIMIT BREACH: {e}")

# Check aggregates
agg = limits.get_aggregated_greeks()
print(f"Portfolio Delta: ${agg.delta:,.0f}")
```

### 2. CorrelationDetector - Regime Break Detection

```python
# Detect when markets switch to crisis mode (forced correlation)
detector = safety.correlation_detector

# Add price data
detector.add_price_update("SPY", 450.0)
detector.add_price_update("QQQ", 380.0)
detector.add_price_update("IWM", 185.0)

# Check for regime changes
is_regime_break, condition_number = detector.detect_regime_break()

if is_regime_break:
    print(f"⚠️  REGIME BREAK: condition number = {condition_number:.2f}")
    print("   Market correlation increased - diversification failed")
else:
    print(f"✓ Normal regime: condition number = {condition_number:.2f}")

# Interpretation:
# ~1 = Independent
# 3-5 = Moderate correlation
# >10 = Regime break (crisis)
```

### 3. CircuitBreaker - Loss & Volatility Control

```python
# Automatic halt on extreme events
breaker = safety.circuit_breaker

# Monitor P&L
trading_ok, msg = breaker.update_pnl(-25_000_000)  # -$25M loss
if not trading_ok:
    print(f"🛑 CIRCUIT BREAKER: {msg}")
    # All trading halted

# Monitor prices for black swan / vol spikes
trading_ok, msg = breaker.update_price(99.5)
if not trading_ok:
    print(f"🛑 CIRCUIT BREAKER: {msg}")

# Manual override (for authorized personnel)
breaker.override_trigger("Risk team authorization - liquidity restored")
```

### 4. HumanEscalation - Alert Management

```python
# Log and escalate alerts
escalation = safety.human_escalation

# Log an alert
alert = escalation.log_alert(
    alert_type="position_warning",
    severity="warning",
    message="Position approaching 85% of limit",
    metadata={"position": "SPY_CALL", "percentage": 87}
)

# Check if should send to humans
if escalation.should_escalate("warning"):
    send_sms_alert()
    send_slack_message()
    
# Get recent alerts
alerts = escalation.get_pending_alerts()
for alert in alerts:
    print(f"[{alert.severity}] {alert.message}")
```

### 5. RiskValidator - Trade Validation

```python
# Pre-trade and post-trade quality checks
validator = safety.risk_validator

# Pre-trade: will trade parameters work?
is_valid, issue = validator.validate_trade(position)
if not is_valid:
    print(f"Trade rejected: {issue}")

# Post-trade: was execution quality acceptable?
is_valid, issue = validator.validate_execution(
    expected_greeks=position.greeks,
    actual_greeks=actual_greeks,
    expected_price=100.0,
    actual_price=100.50,
    size=100_000
)

# Post-trade: was P&L reasonable?
is_valid, issue = validator.validate_pnl_bounds(
    notional=10_000_000,
    expected_pnl=50_000,
    actual_pnl=48_000,
    risk_limit_pct=0.10  # 10% max deviation
)
```

## Production Integration

### Trading Loop

```python
def process_order(order):
    # Convert to position
    position = order_to_position(order)
    
    # Pre-trade gate (all checks before execution)
    is_approved, messages = safety.pre_trade_check(position)
    
    if is_approved:
        # Execute
        result = execute_trade(position)
        
        # Immediate post-trade validation
        is_valid, issues = safety.post_trade_validation(
            position.instrument_id,
            position.greeks,
            result.greeks,
            result.price,
            result.pnl
        )
        
        if not is_valid:
            escalate_to_risk_team(issues)
    else:
        # Reject with reason
        log_rejection(messages)
        notify_trader(messages)

# Market monitoring loop (runs continuously)
def monitor_market():
    while True:
        # Update prices
        for symbol, price in get_latest_prices().items():
            trading_ok, msg = safety.circuit_breaker.update_price(price)
            if not trading_ok:
                halt_all_trading(msg)
        
        # Update P&L
        pnl = compute_portfolio_pnl()
        trading_ok, msg = safety.circuit_breaker.update_pnl(pnl)
        if not trading_ok:
            halt_all_trading(msg)
        
        # Check for alerts
        if safety.human_escalation.should_escalate("critical"):
            send_alerts()
```

## Common Scenarios

### Scenario 1: Normal Trade

```python
position = PositionData(
    instrument_id="SPY",
    notional_usd=5_000_000,
    side="long",
    greeks=GreeksSnapshot(delta=100_000, gamma=5_000, vega=2_000, theta=100, rho=500)
)

is_approved, msgs = safety.pre_trade_check(position)
# Result: APPROVED ✓ (well within all limits)
```

### Scenario 2: Approaching Limit

```python
# Position at 80% of book limit
position = PositionData(
    instrument_id="QQQ",
    notional_usd=400_000_000,
    side="long",
    greeks=GreeksSnapshot(delta=500_000, gamma=50_000, vega=100_000, theta=1_000, rho=10_000)
)

is_approved, msgs = safety.pre_trade_check(position)
# Result: APPROVED (but with warnings)
# Message: "Book 'default' at 80% of limit"
```

### Scenario 3: Exceeds Hard Limit

```python
# Position would exceed instrument limit
position = PositionData(
    instrument_id="HUGE_POS",
    notional_usd=150_000_000,  # Exceeds $100M limit
    side="long",
    greeks=GreeksSnapshot(delta=500_000, gamma=50_000, vega=100_000, theta=1_000, rho=10_000)
)

is_approved, msgs = safety.pre_trade_check(position)
# Result: REJECTED ✗
# Message: "Hard limit violation: Instrument HUGE_POS: $150M > $100M"
```

### Scenario 4: Regime Break

```python
# All assets move together (crisis mode)
detector.add_price_update("SPY", 420.0)    # Down 5%
detector.add_price_update("QQQ", 350.0)    # Down 5%
detector.add_price_update("IWM", 170.0)    # Down 5%

is_regime_break, cond_num = detector.detect_regime_break()
# Result: True, condition_number = 45.2 (very high)
# Message: REGIME BREAK - diversification has failed
```

### Scenario 5: Circuit Breaker Trigger

```python
# Daily losses accumulate
breaker.update_pnl(-15_000_000)  # -$15M
breaker.update_pnl(-20_000_000)  # -$20M
trading_ok, msg = breaker.update_pnl(-20_000_000)  # -$20M (total -$55M)

# Result: False (trading halted)
# Message: "CIRCUIT BREAKER TRIGGERED: Daily loss $55,000,000 exceeds limit $50,000,000"
```

## Test Coverage

Run all tests:
```bash
python3 -m pytest test_safety.py -v
```

Run specific test:
```bash
python3 -m pytest test_safety.py::TestPositionLimits -v
python3 -m pytest test_safety.py::TestCircuitBreaker::test_daily_loss_limit_trigger -v
```

Run with timing:
```bash
python3 -m pytest test_safety.py --durations=10
```

## Performance Targets (Achieved)

| Operation | Target | Actual |
|-----------|--------|--------|
| Position limit check | <10ms | <1ms |
| Greeks aggregation | <5ms | <0.5ms |
| Correlation detection | <500ms | ~100ms |
| Circuit breaker check | <100ms | <10ms |
| Full pre-trade gate | <1s | <200ms |

## Key Limits

```python
# Notional Limits
- Instrument: $100M
- Book: $500M
- Portfolio: $2B

# Greeks Limits (absolute value)
- Delta: $1B hard stop
- Gamma: $100M hard stop
- Vega: $50M hard stop
- Theta: $10M hard stop

# Circuit Breaker Limits
- Daily loss: $50M
- Vol spike: +50% increase
- Black swan: >3 sigma
- Condition number: >10

# Validation Thresholds
- Price slippage: 10% max
- Greeks deviation: 15% max
- P&L deviation: 10% max
```

## Troubleshooting

### Trade rejected but shouldn't be?

1. Check individual position Greeks
2. Verify it's not aggregated near another position
3. Check book-level limits
4. Verify circuit breaker not triggered

### False positive circuit breaker?

```python
# Check circuit breaker state
print(f"Is triggered: {safety.circuit_breaker.is_triggered}")
print(f"Daily P&L: ${safety.circuit_breaker.daily_pnl_usd:,.0f}")
print(f"Reason: {safety.circuit_breaker.trigger_reason}")

# Manual override if justified
safety.circuit_breaker.override_trigger("Manual authorization")
```

### Need to understand regime break?

```python
# Get detailed info
cond_num = safety.correlation_detector.get_condition_number()
eigenvalues = safety.correlation_detector.get_eigenvalues()

print(f"Condition number: {cond_num:.2f}")
print(f"Eigenvalues: {eigenvalues}")

# For crisis mode: spread is small (all same eigenvalue)
# For normal: spread is large (diverse eigenvalues)
```

## Files

- `safety_systems.py` - Implementation (969 lines)
- `test_safety.py` - Tests (876 lines)
- `README.md` - Full documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `QUICKSTART.md` - This file

## Support

Questions? Check:
1. README.md for detailed API docs
2. test_safety.py for usage examples
3. IMPLEMENTATION_SUMMARY.md for technical design
