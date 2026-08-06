"""
Regime Detector: Market Regime Classification
==============================================

Detects current market regime using volatility, skew, term structure,
and event data. Integrates with KnowledgeGraph for regime relationships.

Market Regimes:
1. bull_low_vol: Rising prices, low volatility - favorable gamma scalping
2. bull_high_vol: Rising but volatile - momentum with hedging
3. bear_low_vol: Declining prices, low vol - mean reversion opportunities
4. bear_high_vol: Declining and volatile - defensive, event-driven
5. stress: Extreme dislocations, correlation spikes - arb opportunities
6. normal: Baseline regime - neutral positioning

Regime Detection:
- Hourly updates on vol jumps >5%
- Weekly baseline updates
- Event-triggered updates
- Integration with KG regime relationships
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class RegimeType(Enum):
    """Market regime classification."""
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    STRESS = "stress"
    NORMAL = "normal"


class RegimeDetector:
    """
    Detects market regime from volatility, skew, term structure, and events.

    Maintains regime history and integrates with KnowledgeGraph for
    regime-strategy relationships.
    """

    def __init__(self, use_kg: bool = True):
        """
        Initialize regime detector.

        Args:
            use_kg: If True, try to use KnowledgeGraph (optional)
        """
        self.use_kg = use_kg
        self.kg = None

        if use_kg:
            self._init_kg()

        # Regime thresholds
        self.vol_threshold_low = 0.15  # 15% vol threshold
        self.vol_threshold_high = 0.40  # 40% vol threshold
        self.skew_threshold = 0.5  # Skew magnitude threshold
        self.term_structure_threshold = 0.10  # Term structure slope threshold

        # Regime history
        self.regime_history: List[Tuple[str, datetime, float]] = []  # (regime, timestamp, confidence)
        self.current_regime = RegimeType.NORMAL.value
        self.current_regime_confidence = 0.5

        logger.info(f"Initialized RegimeDetector (use_kg={use_kg})")

    def _init_kg(self):
        """Try to initialize KnowledgeGraph connection."""
        try:
            import sys
            sys.path.insert(0, '/workspace/group1-rag/kg')
            from kg_client import create_client

            self.kg = create_client(use_mock=True)
            logger.info("Connected to KnowledgeGraph")
        except Exception as e:
            logger.warning(f"Could not initialize KG: {e}. Using standalone mode.")
            self.use_kg = False

    def detect_regime(
        self,
        volatility: float,
        skew: float,
        term_structure_slope: float,
        price_momentum: float,
        vol_of_vol: float,
        events: List[str],
        correlation_regime: str = "normal"
    ) -> Tuple[str, float]:
        """
        Detect current market regime.

        Args:
            volatility: Current realized/implied vol [0, 1]
            skew: Skew level [-1, 1] (negative = put skew)
            term_structure_slope: Term structure slope
            price_momentum: Price momentum [-1, 1]
            vol_of_vol: Volatility of volatility
            events: List of active events
            correlation_regime: Correlation state

        Returns:
            (regime_label, confidence)
        """
        # Check for stress conditions first
        if self._is_stress(volatility, skew, vol_of_vol, correlation_regime, events):
            confidence = 0.9 if volatility > 0.50 else 0.75
            self._update_regime(RegimeType.STRESS.value, confidence)
            return (RegimeType.STRESS.value, confidence)

        # Determine trend direction
        is_bullish = price_momentum > 0.2

        # Classify based on volatility level
        if volatility < self.vol_threshold_low:
            # Low vol regime
            if is_bullish:
                regime = RegimeType.BULL_LOW_VOL.value
            else:
                regime = RegimeType.BEAR_LOW_VOL.value
            confidence = 0.85 - (0.1 if events else 0.0)

        elif volatility > self.vol_threshold_high:
            # High vol regime
            if is_bullish:
                regime = RegimeType.BULL_HIGH_VOL.value
            else:
                regime = RegimeType.BEAR_HIGH_VOL.value
            confidence = 0.80 - (0.1 if events else 0.0)

        else:
            # Normal regime (in between)
            regime = RegimeType.NORMAL.value
            confidence = 0.7

        # Adjust confidence based on term structure stability
        if abs(term_structure_slope) > self.term_structure_threshold:
            confidence -= 0.1  # Less confident if term structure unusual

        # Adjust based on events
        if events:
            confidence -= 0.05

        # Clamp confidence
        confidence = max(0.1, min(1.0, confidence))

        self._update_regime(regime, confidence)
        return (regime, confidence)

    def _is_stress(
        self,
        volatility: float,
        skew: float,
        vol_of_vol: float,
        correlation_regime: str,
        events: List[str]
    ) -> bool:
        """
        Check if stress regime conditions are present.

        Stress indicators:
        - Vol extremely high (>50%)
        - Extreme skew (>0.8)
        - Vol-of-vol spiked (>0.4)
        - Correlation regime is stress
        - Critical events (crash, gap, etc.)
        """
        vol_extreme = volatility > 0.50
        skew_extreme = abs(skew) > 0.8
        vol_of_vol_high = vol_of_vol > 0.4
        correlation_stress = correlation_regime == "stress"
        critical_events = any(
            e in ["crash", "gap_move", "circuit_breaker", "halt"]
            for e in events
        )

        # Stress if multiple indicators present
        stress_signals = sum([
            vol_extreme,
            skew_extreme,
            vol_of_vol_high,
            correlation_stress,
            critical_events
        ])

        return stress_signals >= 2

    def _update_regime(self, regime: str, confidence: float):
        """Update current regime and record change."""
        old_regime = self.current_regime
        self.current_regime = regime
        self.current_regime_confidence = confidence

        if regime != old_regime:
            logger.info(
                f"Regime shift: {old_regime} -> {regime} "
                f"(confidence={confidence:.2%})"
            )
            self.regime_history.append((regime, datetime.utcnow(), confidence))

    def get_regime_strength(self) -> Dict[str, float]:
        """
        Get strength of current regime across indicators.

        Returns:
            Dict of indicator -> strength [0, 1]
        """
        return {
            "current_regime_confidence": self.current_regime_confidence,
            "regime_stability": self._calculate_regime_stability(),
            "vol_extremeness": self._calculate_vol_extremeness(),
        }

    def _calculate_regime_stability(self) -> float:
        """Calculate stability of current regime (frequency of changes)."""
        if len(self.regime_history) < 2:
            return 0.5  # Default to neutral

        # Count regime changes in last 10 observations
        recent = self.regime_history[-10:]
        regime_changes = sum(1 for i in range(1, len(recent)) if recent[i][0] != recent[i-1][0])

        # Stability = 1 - (changes / max_possible_changes)
        stability = 1.0 - (regime_changes / len(recent))
        return max(0.0, min(1.0, stability))

    def _calculate_vol_extremeness(self) -> float:
        """Calculate how extreme current vol is historically."""
        # For now, return neutral. In real system, would track historical vol
        return 0.5

    def get_regime_history(self, last_n: int = 20) -> List[Dict[str, Any]]:
        """Get recent regime history."""
        return [
            {
                "timestamp": ts.isoformat(),
                "regime": regime,
                "confidence": conf
            }
            for regime, ts, conf in self.regime_history[-last_n:]
        ]

    def query_regime_strategies(self, regime: str) -> List[Dict[str, Any]]:
        """
        Query KnowledgeGraph for strategies optimal in this regime.

        Returns:
            List of strategies with confidence scores
        """
        if not self.kg:
            logger.warning("KG not available; skipping strategy query")
            return []

        try:
            strategies = self.kg.query_strategies_by_regime(regime)
            return strategies
        except Exception as e:
            logger.error(f"Failed to query strategies for regime {regime}: {e}")
            return []

    def get_regime_opportunities(self, regime: str) -> List[Dict[str, Any]]:
        """Get trading opportunities available in this regime."""
        # This would integrate with KG to find opportunities
        # For now, return empty
        return []

    def export_regime_history(self, filepath: str) -> bool:
        """Export regime detection history."""
        import json

        try:
            export = {
                "exported_at": datetime.utcnow().isoformat(),
                "current_regime": self.current_regime,
                "current_confidence": self.current_regime_confidence,
                "history": [
                    {
                        "timestamp": ts.isoformat(),
                        "regime": regime,
                        "confidence": conf
                    }
                    for regime, ts, conf in self.regime_history
                ]
            }

            with open(filepath, 'w') as f:
                json.dump(export, f, indent=2)

            logger.info(f"Exported regime history to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export regime history: {e}")
            return False

    def __repr__(self) -> str:
        return (
            f"RegimeDetector("
            f"regime={self.current_regime}, "
            f"confidence={self.current_regime_confidence:.2%}, "
            f"history_len={len(self.regime_history)})"
        )
