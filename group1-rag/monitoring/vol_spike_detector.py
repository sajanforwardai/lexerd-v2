"""
Volatility Spike Detector

Monitors rolling realized volatility against 30-day baseline.
Trigger: current vol >1.5x baseline for 5+ minutes = spike alert
Attaches spike to market events (Fed, earnings, etc.)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class VolatilitySnapshot:
    """Intraday volatility measurement."""
    timestamp: datetime
    instrument: str
    price: float
    returns: List[float]  # Recent tick returns
    realized_vol: float  # Annualized realized volatility


@dataclass
class VolatilitySpike:
    """Detected volatility spike event."""
    timestamp: datetime
    instrument: str
    baseline_vol: float  # 30-day rolling vol
    spike_vol: float  # Current vol during spike
    spike_ratio: float  # spike_vol / baseline_vol
    duration_minutes: int  # How long spike lasted
    market_event: Optional[str] = None  # "fed", "earnings", "data_release", etc.
    related_instruments: List[str] = field(default_factory=list)  # Correlated spikes
    severity: str = "WARNING"  # "INFO", "WARNING", "CRITICAL"


class VolatilityBaselineCalculator:
    """Calculate rolling volatility baseline."""

    def __init__(self, window_days: int = 30):
        """Initialize baseline calculator.

        Args:
            window_days: Rolling window for baseline (30 days = typical)
        """
        self.window_days = window_days
        self.daily_returns: Dict[str, deque] = {}  # instrument -> deque of daily returns

    def update(self, instrument: str, daily_return: float) -> float:
        """Update baseline with daily return.

        Args:
            instrument: Instrument identifier
            daily_return: Daily return for this instrument

        Returns:
            Current rolling realized volatility (annualized)
        """
        if instrument not in self.daily_returns:
            self.daily_returns[instrument] = deque(maxlen=self.window_days)

        self.daily_returns[instrument].append(daily_return)

        # Calculate annualized realized volatility
        if len(self.daily_returns[instrument]) >= 5:  # Need minimum observations
            returns = np.array(list(self.daily_returns[instrument]))
            daily_vol = np.std(returns)
            annual_vol = daily_vol * np.sqrt(252)  # 252 trading days
            return annual_vol
        return 0.0

    def get_baseline(self, instrument: str) -> float:
        """Get current baseline volatility.

        Args:
            instrument: Instrument identifier

        Returns:
            Annualized realized volatility
        """
        if instrument not in self.daily_returns or not self.daily_returns[instrument]:
            return 0.0

        returns = np.array(list(self.daily_returns[instrument]))
        if len(returns) >= 5:
            daily_vol = np.std(returns)
            return daily_vol * np.sqrt(252)
        return 0.0


class VolatilitySpikeDetector:
    """Detect and alert on volatility spikes."""

    # Configuration
    SPIKE_THRESHOLD_RATIO = 1.5  # 1.5x baseline = spike
    SPIKE_DURATION_THRESHOLD_MIN = 5  # Must persist 5+ minutes
    CRITICAL_SPIKE_RATIO = 2.5  # 2.5x = critical
    ALERT_COOLDOWN_SEC = 60  # Don't re-alert within 60s

    def __init__(self):
        """Initialize spike detector."""
        self.baseline_calc = VolatilityBaselineCalculator()
        self.spikes_active: Dict[str, datetime] = {}  # instrument -> spike start time
        self.recent_alerts: List[VolatilitySpike] = []
        self.last_alert_time: Dict[str, datetime] = {}  # instrument -> last alert time

    def update(self, snapshot: VolatilitySnapshot) -> Optional[VolatilitySpike]:
        """Process volatility snapshot and detect spikes.

        Args:
            snapshot: VolatilitySnapshot with current vol measurement

        Returns:
            VolatilitySpike alert if spike detected, else None
        """
        instrument = snapshot.instrument
        baseline = self.baseline_calc.get_baseline(instrument)

        if baseline == 0:
            # Not enough data yet
            return None

        spike_ratio = snapshot.realized_vol / baseline if baseline > 0 else 0

        # Check for spike initiation
        if spike_ratio >= self.SPIKE_THRESHOLD_RATIO:
            if instrument not in self.spikes_active:
                # New spike starting
                self.spikes_active[instrument] = snapshot.timestamp
                logger.info(
                    f"VOL SPIKE START: {instrument} vol {snapshot.realized_vol:.1%} "
                    f"vs baseline {baseline:.1%} ({spike_ratio:.1f}x)"
                )

            # Check if spike has persisted long enough
            spike_start = self.spikes_active[instrument]
            duration_min = (snapshot.timestamp - spike_start).total_seconds() / 60

            if duration_min >= self.SPIKE_DURATION_THRESHOLD_MIN:
                # Generate alert if not on cooldown
                if self._should_alert(instrument, snapshot.timestamp):
                    spike_alert = VolatilitySpike(
                        timestamp=snapshot.timestamp,
                        instrument=instrument,
                        baseline_vol=baseline,
                        spike_vol=snapshot.realized_vol,
                        spike_ratio=spike_ratio,
                        duration_minutes=int(duration_min),
                        severity=self._classify_severity(spike_ratio),
                    )
                    self.recent_alerts.append(spike_alert)
                    self.last_alert_time[instrument] = snapshot.timestamp
                    logger.warning(
                        f"VOL SPIKE ALERT: {instrument} ({int(duration_min)}min) "
                        f"{spike_ratio:.1f}x baseline, severity: {spike_alert.severity}"
                    )
                    return spike_alert

        else:
            # Spike ended
            if instrument in self.spikes_active:
                spike_start = self.spikes_active[instrument]
                duration_min = (snapshot.timestamp - spike_start).total_seconds() / 60
                del self.spikes_active[instrument]
                logger.info(f"VOL SPIKE END: {instrument} after {int(duration_min)} minutes")

        return None

    def _should_alert(self, instrument: str, timestamp: datetime) -> bool:
        """Check if alert should be generated (cooldown check).

        Args:
            instrument: Instrument identifier
            timestamp: Current timestamp

        Returns:
            True if alert should be generated
        """
        if instrument not in self.last_alert_time:
            return True

        time_since_alert = (timestamp - self.last_alert_time[instrument]).total_seconds()
        return time_since_alert >= self.ALERT_COOLDOWN_SEC

    def _classify_severity(self, spike_ratio: float) -> str:
        """Classify spike severity.

        Args:
            spike_ratio: Ratio of spike vol to baseline

        Returns:
            Severity classification
        """
        if spike_ratio >= self.CRITICAL_SPIKE_RATIO:
            return "CRITICAL"
        elif spike_ratio >= 2.0:
            return "WARNING"
        else:
            return "INFO"

    def attach_event(
        self,
        spike: VolatilitySpike,
        event_type: str,
        event_description: str,
    ) -> VolatilitySpike:
        """Attach market event context to spike.

        Args:
            spike: VolatilitySpike to annotate
            event_type: "fed", "earnings", "data_release", "geopolitical", etc.
            event_description: Description of event

        Returns:
            Updated VolatilitySpike
        """
        spike.market_event = event_type
        logger.info(f"Spike attributed to {event_type}: {event_description}")
        return spike

    def correlate_spikes(
        self,
        spike: VolatilitySpike,
        other_instruments: Dict[str, float],  # instrument -> current vol
    ) -> VolatilitySpike:
        """Check for correlated spikes in other instruments.

        Args:
            spike: Primary spike
            other_instruments: Dict of other instruments and their vols

        Returns:
            Updated spike with related instruments
        """
        baselines = {
            inst: self.baseline_calc.get_baseline(inst)
            for inst in other_instruments.keys()
        }

        related = []
        for inst, vol in other_instruments.items():
            baseline = baselines.get(inst, 0)
            if baseline > 0:
                ratio = vol / baseline
                if ratio >= self.SPIKE_THRESHOLD_RATIO * 0.8:  # 80% of threshold
                    related.append(inst)

        if related:
            spike.related_instruments = related
            logger.info(f"Spike correlation detected in: {', '.join(related)}")

        return spike

    def get_spike_history(self, n_recent: int = 100) -> List[Dict]:
        """Get recent spike history.

        Args:
            n_recent: Number of recent spikes

        Returns:
            List of spikes as dicts
        """
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "instrument": s.instrument,
                "baseline_vol": s.baseline_vol,
                "spike_vol": s.spike_vol,
                "ratio": s.spike_ratio,
                "duration_minutes": s.duration_minutes,
                "event": s.market_event,
                "severity": s.severity,
                "related_instruments": s.related_instruments,
            }
            for s in self.recent_alerts[-n_recent:]
        ]

    def get_current_spikes(self) -> Dict[str, Dict]:
        """Get currently active spikes.

        Returns:
            Dict of instrument -> spike info
        """
        result = {}
        for instrument, start_time in self.spikes_active.items():
            baseline = self.baseline_calc.get_baseline(instrument)
            result[instrument] = {
                "instrument": instrument,
                "start_time": start_time.isoformat(),
                "duration_minutes": (datetime.utcnow() - start_time).total_seconds() / 60,
                "baseline_vol": baseline,
            }
        return result

    def is_spiking(self, instrument: str) -> bool:
        """Check if instrument currently spiking.

        Args:
            instrument: Instrument identifier

        Returns:
            True if active spike
        """
        return instrument in self.spikes_active

    def get_spike_intensity(self) -> float:
        """Get market-wide spike intensity (0-1).

        Returns:
            Intensity where 0 = no spikes, 1 = all instruments spiking critically
        """
        if not self.recent_alerts:
            return 0.0

        # Look at last 10 minutes of alerts
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        recent = [a for a in self.recent_alerts if a.timestamp > cutoff]

        if not recent:
            return 0.0

        severity_scores = {
            "INFO": 0.2,
            "WARNING": 0.6,
            "CRITICAL": 1.0,
        }

        avg_severity = np.mean([severity_scores.get(a.severity, 0) for a in recent])
        return min(avg_severity, 1.0)
