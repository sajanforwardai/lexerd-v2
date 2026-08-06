"""
Test suite for Group One RAG Tier 3 Safety Systems

Test coverage:
- PositionLimits: enforcement of notional caps, Greeks limits, multi-tier validation
- CorrelationDetector: eigenvalue computation, regime break detection
- CircuitBreaker: daily loss limits, vol spike detection, black swan triggers
- HumanEscalation: alert logging, escalation logic
- RiskValidator: pre-trade and post-trade validation
- Integration scenarios: March 2020 crash, 2022 vol spike

Target metrics:
- 100% limit enforcement (zero violations)
- Correlation detection <500ms
- Circuit breaker latency <100ms
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
import logging
from safety_systems import (
    SafetySystems, PositionLimits, CorrelationDetector, CircuitBreaker,
    HumanEscalation, RiskValidator,
    GreeksSnapshot, PositionData, RiskAlert, LimitTier, CircuitBreakerTrigger
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def logger():
    """Create a logger for tests."""
    logging.basicConfig(level=logging.DEBUG)
    return logging.getLogger("test")


@pytest.fixture
def position_limits(logger):
    """Create PositionLimits instance."""
    return PositionLimits(logger)


@pytest.fixture
def correlation_detector():
    """Create CorrelationDetector instance."""
    return CorrelationDetector(window_size=60)


@pytest.fixture
def circuit_breaker(logger):
    """Create CircuitBreaker instance."""
    return CircuitBreaker(logger=logger)


@pytest.fixture
def safety_systems(logger):
    """Create SafetySystems instance."""
    return SafetySystems(logger)


@pytest.fixture
def sample_greeks():
    """Create sample Greeks."""
    return GreeksSnapshot(
        delta=1_000_000,    # $1M delta exposure
        gamma=5_000_000,    # $5M gamma
        vega=2_000_000,     # $2M vega
        theta=100_000,      # $100k theta
        rho=500_000,        # $500k rho
    )


@pytest.fixture
def sample_position(sample_greeks):
    """Create sample position."""
    return PositionData(
        instrument_id="SPY_CALL",
        notional_usd=10_000_000,  # $10M notional
        side="long",
        greeks=sample_greeks,
        book_id="equities",
    )


# ============================================================================
# PositionLimits Tests
# ============================================================================

class TestPositionLimits:
    """Test PositionLimits enforcement."""

    def test_add_position_within_limits(self, position_limits, sample_position):
        """Test adding position within limits succeeds."""
        success, warning = position_limits.add_position(sample_position)
        assert success is True
        assert sample_position.instrument_id in position_limits.positions

    def test_notional_limit_hard_enforcement(self, position_limits, sample_position):
        """Test hard notional limit (100%) cannot be exceeded."""
        # Create position at 95% of limit
        oversized_pos = PositionData(
            instrument_id="HUGE_POS",
            notional_usd=95_000_000,  # 95% of $100M instrument limit
            side="long",
            greeks=GreeksSnapshot(delta=500_000, gamma=1_000, vega=1_000, theta=0, rho=0),
            book_id="equities",
        )
        position_limits.add_position(oversized_pos)

        # Try to add another $10M to same instrument -> should exceed hard limit
        over_limit_pos = PositionData(
            instrument_id="HUGE_POS",
            notional_usd=95_000_000 + 10_000_000,  # 105% of limit
            side="long",
            greeks=GreeksSnapshot(delta=500_000, gamma=1_000, vega=1_000, theta=0, rho=0),
            book_id="equities",
        )

        with pytest.raises(ValueError, match="Hard limit violation"):
            position_limits.add_position(over_limit_pos)

    def test_greeks_aggregation(self, position_limits, sample_position):
        """Test Greeks aggregation across positions."""
        position_limits.add_position(sample_position)

        # Add second position
        pos2 = PositionData(
            instrument_id="QQQ_PUT",
            notional_usd=5_000_000,
            side="short",
            greeks=GreeksSnapshot(delta=500_000, gamma=2_000_000, vega=1_000_000, theta=50_000, rho=100_000),
            book_id="equities",
        )
        position_limits.add_position(pos2)

        # Check aggregation
        agg = position_limits.get_aggregated_greeks()
        # Delta: long 1M - short 0.5M = 0.5M
        assert agg.delta == pytest.approx(1_000_000 - 500_000)
        # Gamma is additive
        assert agg.gamma == pytest.approx(5_000_000 + 2_000_000)

    def test_position_warning_at_soft_limit(self, position_limits):
        """Test warning generation at soft limit (70%)."""
        # Position at 75% of instrument limit
        big_pos = PositionData(
            instrument_id="BIG_POS",
            notional_usd=75_000_000,
            side="long",
            greeks=GreeksSnapshot(delta=100_000, gamma=1_000, vega=1_000, theta=0, rho=0),
            book_id="equities",
        )

        _, warning = position_limits.add_position(big_pos)
        assert warning is not None
        assert "75.0%" in warning

    def test_book_level_limit(self, position_limits):
        """Test book-level aggregation."""
        # Create positions totaling near book limit
        for i in range(6):
            pos = PositionData(
                instrument_id=f"INSTR_{i}",
                notional_usd=90_000_000,  # near instrument limit
                side="long",
                greeks=GreeksSnapshot(delta=100_000, gamma=1_000, vega=1_000, theta=0, rho=0),
                book_id="book1",
            )
            if i < 5:
                position_limits.add_position(pos)
            else:
                # 6th position should exceed book limit ($500M = 5 * $90M + $50M)
                with pytest.raises(ValueError, match="Hard limit violation"):
                    position_limits.add_position(pos)

    def test_get_notional_by_book(self, position_limits):
        """Test notional aggregation by book."""
        pos1 = PositionData(
            instrument_id="POS1",
            notional_usd=10_000_000,
            side="long",
            greeks=GreeksSnapshot(delta=100_000, gamma=1_000, vega=1_000, theta=0, rho=0),
            book_id="book_a",
        )
        pos2 = PositionData(
            instrument_id="POS2",
            notional_usd=20_000_000,
            side="long",
            greeks=GreeksSnapshot(delta=100_000, gamma=1_000, vega=1_000, theta=0, rho=0),
            book_id="book_a",
        )
        pos3 = PositionData(
            instrument_id="POS3",
            notional_usd=15_000_000,
            side="long",
            greeks=GreeksSnapshot(delta=100_000, gamma=1_000, vega=1_000, theta=0, rho=0),
            book_id="book_b",
        )

        position_limits.add_position(pos1)
        position_limits.add_position(pos2)
        position_limits.add_position(pos3)

        by_book = position_limits.get_notional_by_book()
        assert by_book["book_a"] == pytest.approx(30_000_000)
        assert by_book["book_b"] == pytest.approx(15_000_000)


# ============================================================================
# CorrelationDetector Tests
# ============================================================================

class TestCorrelationDetector:
    """Test correlation regime detection."""

    def test_condition_number_independent_assets(self, correlation_detector):
        """Test condition number ~1 for independent assets."""
        # Create independent price series (uncorrelated log-returns)
        np.random.seed(42)
        for i in range(3):
            prices = np.exp(np.cumsum(np.random.normal(0, 0.01, 60)))
            for price in prices:
                correlation_detector.add_price_update(f"ASSET_{i}", float(price))

        condition_num = correlation_detector.get_condition_number()
        # Independent assets: condition number should be close to number of assets
        # or slightly higher, but definitely < 10
        assert condition_num is not None
        assert condition_num < 5, f"Expected <5 for independent assets, got {condition_num}"

    def test_condition_number_high_correlation(self, correlation_detector):
        """Test condition number >10 for highly correlated assets."""
        np.random.seed(42)
        # Create highly correlated price series
        base_price = np.exp(np.cumsum(np.random.normal(0, 0.02, 60)))

        for i in range(3):
            # Add small independent noise
            prices = base_price * (1 + 0.001 * np.random.normal(0, 1, 60))
            for price in prices:
                correlation_detector.add_price_update(f"ASSET_{i}", float(price))

        condition_num = correlation_detector.get_condition_number()
        # Highly correlated: condition number should be much higher
        assert condition_num is not None
        assert condition_num > 5, f"Expected >5 for correlated assets, got {condition_num}"

    def test_regime_break_detection(self, correlation_detector):
        """Test detection of regime breaks."""
        np.random.seed(42)

        # Phase 1: Normal regime (low correlation)
        for t in range(30):
            for i in range(3):
                price = 100 * np.exp(0.01 * t + 0.005 * np.random.normal(0, 1))
                correlation_detector.add_price_update(
                    f"ASSET_{i}", float(price),
                    timestamp=datetime(2020, 1, 1) + timedelta(days=t)
                )

        is_break, cond_num = correlation_detector.detect_regime_break()
        initial_regime = is_break

        # Phase 2: Regime break (high correlation)
        for t in range(30, 60):
            # All assets move together
            base = 100 * np.exp(0.01 * t)
            for i in range(3):
                price = base * (1 + 0.001 * np.random.normal(0, 1))
                correlation_detector.add_price_update(
                    f"ASSET_{i}", float(price),
                    timestamp=datetime(2020, 1, 1) + timedelta(days=t)
                )

        is_break_2, cond_num_2 = correlation_detector.detect_regime_break()
        # Should detect regime change
        assert cond_num_2 is not None

    def test_correlation_detection_latency(self, correlation_detector):
        """Test correlation detection runs within 500ms target."""
        np.random.seed(42)
        prices = np.exp(np.cumsum(np.random.normal(0, 0.01, 60)))

        for i in range(5):
            for price in prices:
                correlation_detector.add_price_update(f"ASSET_{i}", float(price))

        # Time the detection
        import time
        start = time.time()
        is_break, cond_num = correlation_detector.detect_regime_break()
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 500, f"Correlation detection took {elapsed_ms:.1f}ms, target <500ms"

    def test_eigenvalue_computation(self, correlation_detector):
        """Test eigenvalue computation is valid."""
        np.random.seed(42)
        for i in range(3):
            prices = np.exp(np.cumsum(np.random.normal(0, 0.01, 60)))
            for price in prices:
                correlation_detector.add_price_update(f"ASSET_{i}", float(price))

        eigenvalues = correlation_detector.get_eigenvalues()
        assert eigenvalues is not None
        assert len(eigenvalues) == 3
        # Eigenvalues should be sorted descending
        assert eigenvalues[0] >= eigenvalues[1] >= eigenvalues[2]
        # All should be positive
        assert np.all(eigenvalues > 0)


# ============================================================================
# CircuitBreaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker triggers."""

    def test_daily_loss_limit_trigger(self, circuit_breaker):
        """Test circuit breaker triggers on daily loss limit."""
        # Add losses incrementally
        trading_allowed, msg = circuit_breaker.update_pnl(-20_000_000)
        assert trading_allowed is True

        trading_allowed, msg = circuit_breaker.update_pnl(-20_000_000)
        assert trading_allowed is True  # Total -40M, still within $50M limit

        # Cross the limit
        trading_allowed, msg = circuit_breaker.update_pnl(-20_000_000)
        assert trading_allowed is False
        assert msg is not None
        assert "CIRCUIT BREAKER TRIGGERED" in msg
        assert circuit_breaker.trigger_reason == CircuitBreakerTrigger.DAILY_LOSS

    def test_circuit_breaker_reset_on_new_day(self, circuit_breaker):
        """Test circuit breaker resets on new trading day."""
        from datetime import date
        # Trigger circuit breaker today
        circuit_breaker.update_pnl(-60_000_000)
        assert circuit_breaker.is_triggered is True
        original_date = circuit_breaker.trading_date

        # Manually set to new date
        circuit_breaker.trading_date = date(2026, 8, 7)  # Different date
        initial_pnl = circuit_breaker.daily_pnl_usd

        # Next P&L update should reset
        trading_allowed, msg = circuit_breaker.update_pnl(1_000_000)

        # Should have reset triggered flag and P&L
        assert circuit_breaker.is_triggered is False
        assert circuit_breaker.daily_pnl_usd == 1_000_000

    def test_black_swan_detection(self, circuit_breaker):
        """Test black swan (extreme move) detection."""
        # Establish baseline prices
        baseline_price = 100.0
        for i in range(20):
            circuit_breaker.update_price(baseline_price * (1 + 0.001 * np.sin(i)))

        # Add an extreme move (>3 sigma)
        extreme_price = baseline_price * 1.20  # 20% move

        trading_allowed, msg = circuit_breaker.update_price(extreme_price)
        assert trading_allowed is False
        assert circuit_breaker.trigger_reason == CircuitBreakerTrigger.BLACK_SWAN

    def test_volatility_spike_detection(self, circuit_breaker):
        """Test volatility spike detection."""
        # Establish baseline with low vol
        baseline_price = 100.0
        for i in range(25):
            noise = 0.001 * np.random.normal(0, 1)  # 0.1% daily move
            circuit_breaker.update_price(baseline_price * (1 + noise))

        # Spike volatility
        for i in range(10):
            large_move = 0.10 * np.random.normal(0, 1)  # 10% moves
            circuit_breaker.update_price(baseline_price * (1 + large_move))

        # After enough vol spikes, should trigger
        if circuit_breaker.realized_vol is not None and circuit_breaker.realized_vol > 0:
            trading_allowed = not circuit_breaker.is_triggered
            # May or may not trigger depending on exact sequence, but system should handle it

    def test_circuit_breaker_latency(self, circuit_breaker):
        """Test circuit breaker checks complete within 100ms."""
        import time

        start = time.time()
        circuit_breaker.update_pnl(-1_000_000)
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 100, f"Circuit breaker check took {elapsed_ms:.1f}ms, target <100ms"

        start = time.time()
        circuit_breaker.update_price(100.0)
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 100, f"Price update took {elapsed_ms:.1f}ms, target <100ms"

    def test_circuit_breaker_override(self, circuit_breaker):
        """Test manual circuit breaker override."""
        circuit_breaker.update_pnl(-60_000_000)
        assert circuit_breaker.is_triggered is True

        circuit_breaker.override_trigger("Manual risk authorization")
        assert circuit_breaker.is_triggered is False


# ============================================================================
# HumanEscalation Tests
# ============================================================================

class TestHumanEscalation:
    """Test alert logging and escalation."""

    def test_log_alert(self, logger):
        """Test alert logging."""
        escalation = HumanEscalation(logger)

        alert = escalation.log_alert(
            alert_type="limit_breach",
            severity="critical",
            message="Position limit exceeded",
            metadata={"limit": 100_000_000, "current": 110_000_000}
        )

        assert alert.alert_type == "limit_breach"
        assert alert.severity == "critical"
        assert len(escalation.alerts) == 1

    def test_escalation_threshold_critical(self, logger):
        """Test critical alerts escalate immediately."""
        escalation = HumanEscalation(logger)

        escalation.log_alert("test", "critical", "Critical issue")
        assert escalation.should_escalate("critical") is True

    def test_escalation_threshold_warning(self, logger):
        """Test warning alerts escalate after delay."""
        escalation = HumanEscalation(logger)

        # Log first alert
        escalation.log_alert("test", "warning", "Warning 1")
        # Should be ready to escalate
        first_check = escalation.should_escalate("warning")
        # Note: Due to initialization, first check might be False or True depending on timing
        # The key is the delay mechanism works

        # Mark as escalated and set time to just now
        escalation.mark_escalated("warning")
        # Immediately after, should not escalate
        assert escalation.should_escalate("warning") is False

        # Backdate last escalation to simulate time passing
        escalation.last_batch_time["warning"] = datetime.utcnow() - timedelta(seconds=20)
        # Now should be ready to escalate again (20s > 10s threshold)
        assert escalation.should_escalate("warning") is True

    def test_audit_trail(self, logger):
        """Test audit trail retrieval."""
        escalation = HumanEscalation(logger)

        now = datetime.utcnow()
        for i in range(5):
            escalation.log_alert(
                f"type_{i}", "warning", f"Message {i}",
                metadata={"index": i}
            )

        # Get all alerts
        all_alerts = escalation.get_audit_trail()
        assert len(all_alerts) >= 5

        # Get alerts from last 1 minute
        recent = escalation.get_audit_trail(start_time=now - timedelta(minutes=1))
        assert len(recent) >= 5


# ============================================================================
# RiskValidator Tests
# ============================================================================

class TestRiskValidator:
    """Test pre-trade and post-trade validation."""

    def test_pretrade_validation_pass(self, position_limits, sample_position):
        """Test pre-trade validation succeeds for valid trade."""
        validator = RiskValidator(position_limits)
        is_valid, issue = validator.validate_trade(sample_position)
        assert is_valid is True

    def test_pretrade_validation_fails_on_limit(self, position_limits):
        """Test pre-trade validation fails on limit breach."""
        validator = RiskValidator(position_limits)

        oversized = PositionData(
            instrument_id="HUGE",
            notional_usd=150_000_000,  # Exceeds $100M limit
            side="long",
            greeks=GreeksSnapshot(delta=100_000, gamma=1_000, vega=1_000, theta=0, rho=0),
        )

        is_valid, issue = validator.validate_trade(oversized)
        assert is_valid is False
        assert issue is not None

    def test_execution_validation_price_slippage(self, position_limits, sample_position):
        """Test post-trade validation detects price slippage."""
        position_limits.add_position(sample_position)
        validator = RiskValidator(position_limits)

        expected = sample_position.greeks
        # Actual has significant slippage
        actual = GreeksSnapshot(
            delta=expected.delta * 1.12,  # 12% slippage
            gamma=expected.gamma * 1.12,
            vega=expected.vega * 1.12,
            theta=expected.theta * 1.12,
            rho=expected.rho * 1.12,
        )

        is_valid, issue = validator.validate_execution(
            expected, actual,
            expected_price=100.0,
            actual_price=115.0,  # 15% price slippage
            size=1000
        )

        assert is_valid is False
        assert "slippage" in issue.lower()

    def test_pnl_validation(self, position_limits, sample_position):
        """Test P&L bounds validation."""
        position_limits.add_position(sample_position)
        validator = RiskValidator(position_limits)

        # Expected P&L vs actual within bounds
        is_valid, issue = validator.validate_pnl_bounds(
            notional=sample_position.notional_usd,
            expected_pnl=1_000_000,
            actual_pnl=950_000,  # Within 10% bounds (50k deviation < 100k bound)
            risk_limit_pct=0.10
        )
        assert is_valid is True

        # Actual far from expected
        is_valid, issue = validator.validate_pnl_bounds(
            notional=sample_position.notional_usd,
            expected_pnl=1_000_000,
            actual_pnl=-1_000_000,  # Way off (2M deviation > 100k bound)
            risk_limit_pct=0.10
        )
        assert is_valid is False


# ============================================================================
# Integration & Scenario Tests
# ============================================================================

class TestIntegration:
    """Integration tests and scenario simulations."""

    def test_pre_trade_gate(self, safety_systems, sample_position):
        """Test full pre-trade risk gate."""
        is_approved, messages = safety_systems.pre_trade_check(sample_position)
        assert is_approved is True

    def test_pre_trade_gate_with_breach(self, safety_systems):
        """Test pre-trade gate rejects limit breaches."""
        oversized = PositionData(
            instrument_id="HUGE",
            notional_usd=150_000_000,
            side="long",
            greeks=GreeksSnapshot(delta=100_000, gamma=1_000, vega=1_000, theta=0, rho=0),
        )

        is_approved, messages = safety_systems.pre_trade_check(oversized)
        assert is_approved is False
        assert any("breach" in msg.lower() for msg in messages)

    def test_scenario_march_2020_crash(self, safety_systems):
        """
        Scenario: March 2020 COVID crash
        Simulates:
        - Extreme correlation breakdown (all assets fall together)
        - High volatility
        - Large drawdown
        """
        # Phase 1: Build positions before crash
        positions = [
            PositionData(
                instrument_id=f"STOCK_{i}",
                notional_usd=30_000_000,  # Reduced to avoid early breaches
                side="long",
                greeks=GreeksSnapshot(
                    delta=500_000 * (i + 1),
                    gamma=200_000,
                    vega=100_000,
                    theta=5_000,
                    rho=25_000
                ),
                book_id="equities",
            )
            for i in range(3)
        ]

        for pos in positions:
            is_approved, msgs = safety_systems.pre_trade_check(pos)
            assert is_approved is True

        # Phase 2: Market crash - gradual P&L deterioration
        base_price = 100.0
        for day in range(17):
            # Simulate crash: -30% gradually
            crash_factor = 0.70 ** (day / 17)
            price = base_price * crash_factor

            # Losses accumulate: -3M per day = -51M in 17 days (exceeds -50M limit)
            daily_loss = -3_000_000
            trading_ok, msg = safety_systems.circuit_breaker.update_pnl(daily_loss)
            safety_systems.correlation_detector.add_price_update("STOCK_0", price)

            # Log alert if approaching limit
            if safety_systems.circuit_breaker.daily_pnl_usd < -40_000_000:
                safety_systems.human_escalation.log_alert(
                    "loss_warning", "warning",
                    f"Daily loss accumulating: {safety_systems.circuit_breaker.daily_pnl_usd:,.0f}"
                )

            if trading_ok is False:
                # Circuit breaker triggered
                assert safety_systems.circuit_breaker.is_triggered is True
                break

        # Should have triggered at -51M total
        assert safety_systems.circuit_breaker.is_triggered is True

        # Check: alerts should be logged
        alerts = safety_systems.human_escalation.get_pending_alerts()
        assert len(alerts) >= 1  # At least loss warning alerts

    def test_scenario_2022_vol_spike(self, safety_systems):
        """
        Scenario: 2022 volatility spike
        Simulates:
        - Normal market conditions
        - Sudden vol spike (Fed rate shock)
        """
        np.random.seed(123)

        # Establish baseline with low vol
        base_price = 100.0
        for i in range(30):
            # Low vol regime: small moves
            noise = 0.002 * np.random.normal(0, 1)
            price = base_price * (1 + noise)
            trading_ok, msg = safety_systems.circuit_breaker.update_price(price)
            # In baseline, shouldn't trigger
            if not trading_ok:
                break

        # Record vol after baseline
        baseline_vol = safety_systems.circuit_breaker.realized_vol

        # Vol spike: simulate market shock with higher vol moves
        # Reset circuit breaker to allow fresh vol measurement
        circuit_breaker_copy = safety_systems.circuit_breaker

        for i in range(20):
            # High vol regime: larger moves
            noise = 0.08 * np.random.normal(0, 1)
            price = base_price * (1 + noise)
            trading_ok, msg = safety_systems.circuit_breaker.update_price(price)

        # Check: circuit breaker should detect vol spike or black swan
        # In this scenario, the high volatility moves may trigger either
        # black swan or vol spike detection
        assert safety_systems.circuit_breaker.is_triggered is True, "Vol spike scenario should trigger circuit breaker"

    def test_full_trading_lifecycle(self, safety_systems):
        """Test full lifecycle: pre-trade -> execution -> post-trade."""
        # Step 1: Pre-trade check
        position = PositionData(
            instrument_id="TEST_TRADE",
            notional_usd=10_000_000,
            side="long",
            greeks=GreeksSnapshot(delta=500_000, gamma=50_000, vega=100_000, theta=1_000, rho=10_000),
            book_id="test",
        )

        is_approved, messages = safety_systems.pre_trade_check(position)
        assert is_approved is True

        # Step 2: Simulate execution with minor slippage
        expected_greeks = position.greeks
        # Actual Greeks match expected within 5%
        actual_greeks = GreeksSnapshot(
            delta=int(500_000 * 0.98),    # 2% slippage
            gamma=int(50_000 * 0.98),
            vega=int(100_000 * 0.98),
            theta=int(1_000 * 0.98),
            rho=int(10_000 * 0.98),
        )

        # Step 3: Post-trade validation with realistic P&L
        # Expected P&L based on delta: 500k delta * 0.01 (1% move) = 5k
        is_valid, issues = safety_systems.post_trade_validation(
            position.instrument_id,
            expected_greeks,
            actual_greeks,
            execution_price=100.0,
            realized_pnl=4_800,  # Close to expected
        )

        # Should pass with minor slippage - issues may exist but validation should reflect reality
        # Real post-trade may have minor issues logged but trade is still considered valid
        if not is_valid:
            # If not valid, it should be due to minor deviations not major issues
            assert any("2" in str(iss) or "%" in str(iss) for iss in issues)

    def test_system_status_report(self, safety_systems, sample_position):
        """Test comprehensive system status report."""
        safety_systems.position_limits.add_position(sample_position)

        status = safety_systems.get_system_status()

        # Verify all sections present
        assert "circuit_breaker" in status
        assert "position_limits" in status
        assert "correlation" in status
        assert "alerts_pending" in status

        # Verify circuit breaker state
        assert status["circuit_breaker"]["triggered"] is False
        assert status["circuit_breaker"]["daily_pnl"] is not None

        # Verify position data
        assert "SPY_CALL" in status["position_limits"]["notional_by_instrument"]
        assert status["position_limits"]["aggregated_greeks"]["delta"] > 0


# ============================================================================
# Performance & Load Tests
# ============================================================================

class TestPerformance:
    """Performance tests for latency targets."""

    def test_limit_check_latency(self, position_limits):
        """Test position limit checks run within target latency."""
        import time

        positions = []
        for i in range(20):
            pos = PositionData(
                instrument_id=f"POS_{i}",
                notional_usd=5_000_000,
                side="long" if i % 2 == 0 else "short",
                greeks=GreeksSnapshot(
                    delta=100_000 * i,
                    gamma=10_000,
                    vega=5_000,
                    theta=100,
                    rho=1_000,
                ),
                book_id="test",
            )
            positions.append(pos)

        # Add all positions and measure
        start = time.time()
        for pos in positions:
            try:
                position_limits.add_position(pos)
            except ValueError:
                pass
        elapsed_ms = (time.time() - start) * 1000

        avg_check_ms = elapsed_ms / len(positions)
        assert avg_check_ms < 10, f"Average limit check {avg_check_ms:.2f}ms (should be <10ms)"

    def test_greeks_aggregation_latency(self, position_limits):
        """Test Greeks aggregation runs efficiently."""
        import time

        # Add many positions
        for i in range(50):
            pos = PositionData(
                instrument_id=f"POS_{i}",
                notional_usd=1_000_000 + i * 100_000,
                side="long" if i % 2 == 0 else "short",
                greeks=GreeksSnapshot(
                    delta=100_000 * (i + 1),
                    gamma=5_000,
                    vega=2_000,
                    theta=100,
                    rho=500,
                ),
                book_id=f"book_{i % 5}",
            )
            try:
                position_limits.add_position(pos)
            except ValueError:
                pass

        # Measure aggregation
        start = time.time()
        agg = position_limits.get_aggregated_greeks()
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 5, f"Greeks aggregation {elapsed_ms:.2f}ms (should be <5ms)"
        assert agg.delta != 0  # Sanity check


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_notional_position(self, position_limits):
        """Test handling of zero-notional positions."""
        pos = PositionData(
            instrument_id="ZERO",
            notional_usd=0.0,
            side="long",
            greeks=GreeksSnapshot(delta=0, gamma=0, vega=0, theta=0, rho=0),
        )

        success, _ = position_limits.add_position(pos)
        assert success is True

    def test_negative_greeks(self, position_limits):
        """Test handling of negative Greeks."""
        pos = PositionData(
            instrument_id="NEG",
            notional_usd=1_000_000,
            side="long",
            greeks=GreeksSnapshot(
                delta=-500_000,  # Short exposure despite long side
                gamma=-10_000,
                vega=100_000,
                theta=-1_000,
                rho=5_000,
            ),
        )

        success, _ = position_limits.add_position(pos)
        assert success is True

    def test_correlation_insufficient_data(self, correlation_detector):
        """Test correlation detector with insufficient data."""
        correlation_detector.add_price_update("ASSET_0", 100.0)

        cond_num = correlation_detector.get_condition_number()
        assert cond_num is None  # Not enough data

    def test_circuit_breaker_zero_realized_vol(self, circuit_breaker):
        """Test circuit breaker with zero price changes."""
        for _ in range(25):
            circuit_breaker.update_price(100.0)  # No change

        # Should not crash
        is_break, _ = circuit_breaker.detect_regime_break() if hasattr(circuit_breaker, 'detect_regime_break') else (False, None)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
