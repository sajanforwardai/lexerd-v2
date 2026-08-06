"""
Statistical validator for A/B testing with bootstrap resampling.

Tests if Tier 3 outperforms Tier 2 with statistical significance.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
from scipy import stats
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result from statistical validation."""

    # Metrics
    tier2_sharpe: float
    tier3_sharpe: float
    sharpe_difference: float
    p_value: float

    # Bootstrap results
    bootstrap_mean: float  # Mean Sharpe difference from bootstrap
    bootstrap_std: float  # Std of Sharpe difference from bootstrap
    confidence_level: float  # e.g., 0.90
    confidence_interval: Tuple[float, float]  # (lower, upper)

    # Decision
    significant_at_level: bool  # Is p_value < (1 - confidence_level)?
    recommendation: str  # "GO", "CONDITIONAL_GO", or "NO_GO"

    # Metadata
    n_bootstrap: int
    n_observations: int
    min_observations_required: int = 30


class StatisticalValidator:
    """Validate statistical significance of strategy improvements."""

    def __init__(self, confidence_level: float = 0.90, n_bootstrap: int = 1000):
        """Initialize validator.

        Args:
            confidence_level: Confidence level (e.g., 0.90 = 90%)
            n_bootstrap: Number of bootstrap samples
        """
        self.confidence_level = confidence_level
        self.n_bootstrap = n_bootstrap
        self.significance_threshold = 1.0 - confidence_level  # alpha = 0.10 for 90% conf

    def validate_improvement(
        self,
        tier2_returns: List[float],
        tier3_returns: List[float],
        tier2_sharpe: float = None,
        tier3_sharpe: float = None,
    ) -> ValidationResult:
        """Validate if Tier 3 is statistically better than Tier 2.

        Args:
            tier2_returns: Baseline (Tier 2) daily returns
            tier3_returns: Candidate (Tier 3) daily returns
            tier2_sharpe: Pre-calculated Tier 2 Sharpe (optional)
            tier3_sharpe: Pre-calculated Tier 3 Sharpe (optional)

        Returns:
            ValidationResult with statistical tests
        """
        if len(tier2_returns) < 30 or len(tier3_returns) < 30:
            logger.warning(
                f"Insufficient data: Tier2={len(tier2_returns)}, Tier3={len(tier3_returns)}"
            )

        tier2_returns = np.array(tier2_returns)
        tier3_returns = np.array(tier3_returns)

        # Calculate Sharpe ratios if not provided
        if tier2_sharpe is None:
            tier2_sharpe = self._calculate_sharpe(tier2_returns)
        if tier3_sharpe is None:
            tier3_sharpe = self._calculate_sharpe(tier3_returns)

        sharpe_diff = tier3_sharpe - tier2_sharpe

        # Bootstrap resampling for confidence interval
        bootstrap_diffs = self._bootstrap_sharpe_difference(
            tier2_returns, tier3_returns, self.n_bootstrap
        )

        # Calculate statistics from bootstrap
        bootstrap_mean = np.mean(bootstrap_diffs)
        bootstrap_std = np.std(bootstrap_diffs)
        conf_lower = np.percentile(bootstrap_diffs, (1 - self.confidence_level) / 2 * 100)
        conf_upper = np.percentile(
            bootstrap_diffs, (1 - (1 - self.confidence_level) / 2) * 100
        )

        # P-value: proportion of bootstrap samples where Tier 3 < Tier 2
        p_value = np.mean(bootstrap_diffs <= 0)

        # Decision logic
        is_significant = p_value < self.significance_threshold

        recommendation = self._make_recommendation(
            sharpe_diff, p_value, is_significant
        )

        return ValidationResult(
            tier2_sharpe=tier2_sharpe,
            tier3_sharpe=tier3_sharpe,
            sharpe_difference=sharpe_diff,
            p_value=p_value,
            bootstrap_mean=bootstrap_mean,
            bootstrap_std=bootstrap_std,
            confidence_level=self.confidence_level,
            confidence_interval=(conf_lower, conf_upper),
            significant_at_level=is_significant,
            recommendation=recommendation,
            n_bootstrap=self.n_bootstrap,
            n_observations=len(tier2_returns),
            min_observations_required=30,
        )

    def _bootstrap_sharpe_difference(
        self,
        tier2_returns: np.ndarray,
        tier3_returns: np.ndarray,
        n_samples: int,
    ) -> np.ndarray:
        """Bootstrap resample to estimate Sharpe difference distribution.

        Args:
            tier2_returns: Baseline returns
            tier3_returns: Candidate returns
            n_samples: Number of bootstrap samples

        Returns:
            Array of Sharpe differences from bootstrap samples
        """
        differences = []

        for _ in range(n_samples):
            # Resample with replacement
            tier2_sample = np.random.choice(tier2_returns, size=len(tier2_returns), replace=True)
            tier3_sample = np.random.choice(tier3_returns, size=len(tier3_returns), replace=True)

            # Calculate Sharpe for each sample
            sharpe2 = self._calculate_sharpe(tier2_sample)
            sharpe3 = self._calculate_sharpe(tier3_sample)

            differences.append(sharpe3 - sharpe2)

        return np.array(differences)

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """Calculate Sharpe ratio (annualized).

        Risk-free rate: 2% annual
        Trading days: 252
        """
        if len(returns) == 0:
            return 0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0

        annual_return = mean_return * 252
        annual_vol = std_return * np.sqrt(252)
        risk_free = 0.02

        sharpe = (annual_return - risk_free) / annual_vol
        return sharpe

    def _make_recommendation(
        self,
        sharpe_diff: float,
        p_value: float,
        is_significant: bool,
    ) -> str:
        """Make GO/CONDITIONAL_GO/NO_GO recommendation.

        Decision tree:
        - p_value < 0.10 (90% confidence) + positive Sharpe diff → GO
        - 0.10 <= p_value < 0.20 + positive Sharpe diff → CONDITIONAL_GO
        - Negative Sharpe diff → NO_GO
        """
        if not is_significant and sharpe_diff <= 0:
            return "NO_GO"

        if is_significant and sharpe_diff > 0:
            return "GO"

        if sharpe_diff > 0 and p_value < 0.20:
            return "CONDITIONAL_GO"

        return "NO_GO"

    def permutation_test(
        self,
        tier2_returns: List[float],
        tier3_returns: List[float],
        n_permutations: int = 1000,
    ) -> Tuple[float, float]:
        """Permutation test for Sharpe difference.

        Alternative to bootstrap that makes no distributional assumptions.

        Args:
            tier2_returns: Baseline returns
            tier3_returns: Candidate returns
            n_permutations: Number of permutations

        Returns:
            (observed_sharpe_diff, p_value)
        """
        tier2 = np.array(tier2_returns)
        tier3 = np.array(tier3_returns)

        observed_diff = self._calculate_sharpe(tier3) - self._calculate_sharpe(tier2)

        # Combine returns
        combined = np.concatenate([tier2, tier3])
        n_tier2 = len(tier2)

        permutation_diffs = []
        for _ in range(n_permutations):
            # Permute combined returns
            perm_idx = np.random.permutation(len(combined))
            perm_combined = combined[perm_idx]

            # Split into tier2 and tier3 sizes
            perm_tier2 = perm_combined[:n_tier2]
            perm_tier3 = perm_combined[n_tier2:]

            # Calculate Sharpe difference
            perm_diff = self._calculate_sharpe(perm_tier3) - self._calculate_sharpe(perm_tier2)
            permutation_diffs.append(perm_diff)

        permutation_diffs = np.array(permutation_diffs)
        p_value = np.mean(permutation_diffs >= observed_diff)

        return observed_diff, p_value

    def effect_size_cohens_d(
        self,
        tier2_returns: List[float],
        tier3_returns: List[float],
    ) -> float:
        """Calculate Cohen's d effect size.

        Measures practical significance of the difference.

        Args:
            tier2_returns: Baseline returns
            tier3_returns: Candidate returns

        Returns:
            Cohen's d (0.2=small, 0.5=medium, 0.8=large)
        """
        tier2 = np.array(tier2_returns)
        tier3 = np.array(tier3_returns)

        mean_diff = np.mean(tier3) - np.mean(tier2)
        pooled_std = np.sqrt(
            ((len(tier2) - 1) * np.var(tier2, ddof=1) +
             (len(tier3) - 1) * np.var(tier3, ddof=1)) /
            (len(tier2) + len(tier3) - 2)
        )

        if pooled_std == 0:
            return 0

        cohens_d = mean_diff / pooled_std
        return cohens_d

    def required_sample_size(
        self,
        effect_size: float = 0.5,
        alpha: float = 0.10,
        power: float = 0.80,
    ) -> int:
        """Calculate required sample size for desired statistical power.

        Args:
            effect_size: Cohen's d effect size
            alpha: Significance level (default 0.10 for 90% confidence)
            power: Desired power (default 0.80)

        Returns:
            Required number of observations per group
        """
        from scipy.stats import nct

        # Noncentrality parameter
        nc = effect_size * np.sqrt(2)

        # Critical t-value (two-tailed)
        t_crit = stats.t.ppf(1 - alpha / 2, 1000)  # Use large df approximation

        # Find sample size via approximation
        # n = 2 * ((t_crit + t_power) / effect_size) ** 2
        t_power = stats.t.ppf(power, 1000)

        n = 2 * ((t_crit + t_power) / effect_size) ** 2

        return int(np.ceil(n))
