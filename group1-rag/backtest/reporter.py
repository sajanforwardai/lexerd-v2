"""
Results reporter for generating JSON and Markdown reports.

Creates comparison tables and detailed analysis output.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import json
from datetime import datetime

from .backtest_engine import BacktestResult


class ReportFormat(Enum):
    """Report output formats."""
    JSON = "json"
    MARKDOWN = "markdown"
    BOTH = "both"


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    include_trades: bool = True
    include_positions: bool = False
    include_bootstrap_details: bool = True
    decimal_places: int = 4


class ResultsReporter:
    """Generate comprehensive backtest reports."""

    def __init__(self, config: ReportConfig = None):
        """Initialize reporter.

        Args:
            config: Report configuration
        """
        self.config = config or ReportConfig()

    def generate_report(
        self,
        result: BacktestResult,
        format: ReportFormat = ReportFormat.MARKDOWN,
        output_path: Optional[str] = None,
    ) -> str:
        """Generate complete report.

        Args:
            result: BacktestResult from engine
            format: Output format (JSON, Markdown, or both)
            output_path: Optional path to write report

        Returns:
            Report content as string
        """
        if format == ReportFormat.JSON:
            content = self._generate_json_report(result)
        elif format == ReportFormat.MARKDOWN:
            content = self._generate_markdown_report(result)
        else:
            # Both formats
            json_content = self._generate_json_report(result)
            md_content = self._generate_markdown_report(result)
            content = f"{md_content}\n\n---\n## JSON Output\n\n```json\n{json_content}\n```"

        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)

        return content

    def _generate_json_report(self, result: BacktestResult) -> str:
        """Generate JSON report."""
        report_dict = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'backtest_start': result.config.start_date,
                'backtest_end': result.config.end_date,
                'symbol': result.config.symbol,
                'confidence_level': float(result.config.confidence_level),
            },
            'tier2_baseline': {
                'metrics': self._metrics_to_dict(result.tier2_metrics),
                'execution': {
                    'trades': int(len(result.tier2_execution.trades)),
                    'final_value': float(round(result.tier2_execution.final_value, 2)),
                    'cash_balance': float(round(result.tier2_execution.cash_balance, 2)),
                    'transaction_costs': float(round(result.tier2_execution.transaction_costs, 4)),
                },
            },
            'tier3_candidate': {
                'metrics': self._metrics_to_dict(result.tier3_metrics),
                'execution': {
                    'trades': int(len(result.tier3_execution.trades)),
                    'final_value': float(round(result.tier3_execution.final_value, 2)),
                    'cash_balance': float(round(result.tier3_execution.cash_balance, 2)),
                    'transaction_costs': float(round(result.tier3_execution.transaction_costs, 4)),
                },
            },
            'comparison': {
                'sharpe_difference': float(round(result.validation_result.sharpe_difference, self.config.decimal_places)),
                'sharpe_difference_std_error': float(round(result.validation_result.bootstrap_std, self.config.decimal_places)),
                'p_value': float(round(result.validation_result.p_value, self.config.decimal_places)),
                'confidence_interval': [
                    float(round(result.validation_result.confidence_interval[0], self.config.decimal_places)),
                    float(round(result.validation_result.confidence_interval[1], self.config.decimal_places)),
                ],
                'significant_at_90_percent': bool(result.validation_result.significant_at_level),
                'bootstrap_samples': int(result.validation_result.n_bootstrap),
            },
            'decision': {
                'winner': str(result.winner),
                'recommendation': str(result.recommendation),
                'threshold_p_value': 0.10,
            },
        }

        if self.config.include_trades:
            report_dict['tier2_baseline']['trades'] = self._trades_to_dicts(result.tier2_execution.trades)
            report_dict['tier3_candidate']['trades'] = self._trades_to_dicts(result.tier3_execution.trades)

        return json.dumps(report_dict, indent=2)

    def _generate_markdown_report(self, result: BacktestResult) -> str:
        """Generate Markdown report."""
        lines = []

        # Header
        lines.append("# A/B Backtest Report: Tier 2 vs Tier 3")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Symbol:** {result.config.symbol}")
        lines.append(f"**Period:** {result.config.start_date} to {result.config.end_date}")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(self._get_recommendation_text(result.recommendation))
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Winner** | **{result.winner.upper()}** |")
        lines.append(f"| **Sharpe Difference** | {result.validation_result.sharpe_difference:.4f} |")
        lines.append(f"| **P-Value** | {result.validation_result.p_value:.4f} |")
        lines.append(f"| **Confidence Level** | {result.config.confidence_level*100:.0f}% |")
        lines.append(f"| **Significant** | {'✓ YES' if result.validation_result.significant_at_level else '✗ NO'} |")
        lines.append("")

        # Performance Comparison Table
        lines.append("## Performance Comparison")
        lines.append("")
        lines.append(self._create_metrics_table(result))
        lines.append("")

        # Tier 2 Detailed Results
        lines.append("## Tier 2 Baseline Details")
        lines.append("")
        lines.append(self._format_metrics_section(result.tier2_metrics, "Tier 2"))
        lines.append("")
        lines.append(f"**Execution:** {len(result.tier2_execution.trades)} trades | "
                     f"Final Value: ${result.tier2_execution.final_value:,.2f}")
        lines.append("")

        # Tier 3 Detailed Results
        lines.append("## Tier 3 Candidate Details")
        lines.append("")
        lines.append(self._format_metrics_section(result.tier3_metrics, "Tier 3"))
        lines.append("")
        lines.append(f"**Execution:** {len(result.tier3_execution.trades)} trades | "
                     f"Final Value: ${result.tier3_execution.final_value:,.2f}")
        lines.append("")

        # Statistical Analysis
        lines.append("## Statistical Analysis")
        lines.append("")
        lines.append(f"**Bootstrap Samples:** {result.validation_result.n_bootstrap}")
        lines.append(f"**Bootstrap Mean Sharpe Diff:** {result.validation_result.bootstrap_mean:.4f}")
        lines.append(f"**Bootstrap Std Dev:** {result.validation_result.bootstrap_std:.4f}")
        lines.append("")
        lines.append("### Confidence Interval (90%)")
        lines.append(f"Lower bound: {result.validation_result.confidence_interval[0]:.4f}")
        lines.append(f"Upper bound: {result.validation_result.confidence_interval[1]:.4f}")
        lines.append("")

        # Hypothesis Test
        lines.append("### Hypothesis Test")
        lines.append(f"**H0:** Tier 3 Sharpe ≤ Tier 2 Sharpe")
        lines.append(f"**H1:** Tier 3 Sharpe > Tier 2 Sharpe (one-tailed)")
        lines.append(f"**P-Value:** {result.validation_result.p_value:.4f}")
        lines.append(f"**Significance Level:** α = 0.10 (90% confidence)")
        lines.append("")
        if result.validation_result.significant_at_level:
            lines.append("✓ **Result:** Reject H0 - Tier 3 is statistically significantly better at 90% confidence")
        else:
            lines.append("✗ **Result:** Fail to reject H0 - No significant improvement")
        lines.append("")

        # Risk Metrics
        lines.append("## Risk Analysis")
        lines.append("")
        lines.append(f"| Risk Metric | Tier 2 | Tier 3 | Difference |")
        lines.append("|---|---|---|---|")
        lines.append(f"| Max Drawdown | {result.tier2_metrics.max_drawdown:.2f}% | "
                     f"{result.tier3_metrics.max_drawdown:.2f}% | "
                     f"{result.tier3_metrics.max_drawdown - result.tier2_metrics.max_drawdown:.2f}% |")
        lines.append(f"| Volatility | {result.tier2_metrics.volatility:.2f}% | "
                     f"{result.tier3_metrics.volatility:.2f}% | "
                     f"{result.tier3_metrics.volatility - result.tier2_metrics.volatility:.2f}% |")
        lines.append("")

        # Recommendation Text
        lines.append("## Recommendation")
        lines.append("")
        if result.recommendation == "GO":
            lines.append("**GO** - Deploy Tier 3 in production.")
            lines.append("Tier 3 shows statistically significant outperformance with sufficient confidence.")
        elif result.recommendation == "CONDITIONAL_GO":
            lines.append("**CONDITIONAL GO** - Further validation recommended before full deployment.")
            lines.append("Tier 3 shows improvement but statistical confidence is moderate.")
        else:
            lines.append("**NO GO** - Keep Tier 2 as baseline.")
            lines.append("Tier 3 does not demonstrate statistically significant improvement.")

        lines.append("")
        lines.append(f"**Threshold:** p-value < 0.10 required for GO decision")
        lines.append("")

        # Trades (if enabled)
        if self.config.include_trades and result.tier3_execution.trades:
            lines.append("## Tier 3 Sample Trades")
            lines.append("")
            lines.append(self._create_trades_table(result.tier3_execution.trades[:10]))
            lines.append("")

        return "\n".join(lines)

    def _create_metrics_table(self, result: BacktestResult) -> str:
        """Create metrics comparison table."""
        lines = []
        lines.append("| Metric | Tier 2 | Tier 3 | Winner |")
        lines.append("|--------|--------|--------|--------|")
        lines.append(f"| Total Return | {result.tier2_metrics.total_return:.2f}% | "
                     f"{result.tier3_metrics.total_return:.2f}% | "
                     f"{'Tier 3 ↑' if result.tier3_metrics.total_return > result.tier2_metrics.total_return else 'Tier 2 ↓'} |")
        lines.append(f"| Annual Return | {result.tier2_metrics.annual_return:.2f}% | "
                     f"{result.tier3_metrics.annual_return:.2f}% | "
                     f"{'Tier 3 ↑' if result.tier3_metrics.annual_return > result.tier2_metrics.annual_return else 'Tier 2 ↓'} |")
        lines.append(f"| Sharpe Ratio | {result.tier2_metrics.sharpe_ratio:.4f} | "
                     f"{result.tier3_metrics.sharpe_ratio:.4f} | "
                     f"{'**Tier 3 ↑**' if result.tier3_metrics.sharpe_ratio > result.tier2_metrics.sharpe_ratio else '**Tier 2 ↓**'} |")
        lines.append(f"| Sortino Ratio | {result.tier2_metrics.sortino_ratio:.4f} | "
                     f"{result.tier3_metrics.sortino_ratio:.4f} | "
                     f"{'Tier 3 ↑' if result.tier3_metrics.sortino_ratio > result.tier2_metrics.sortino_ratio else 'Tier 2 ↓'} |")
        lines.append(f"| Win Rate | {result.tier2_metrics.win_rate*100:.1f}% | "
                     f"{result.tier3_metrics.win_rate*100:.1f}% | "
                     f"{'Tier 3 ↑' if result.tier3_metrics.win_rate > result.tier2_metrics.win_rate else 'Tier 2 ↓'} |")
        lines.append(f"| Profit Factor | {result.tier2_metrics.profit_factor:.2f} | "
                     f"{result.tier3_metrics.profit_factor:.2f} | "
                     f"{'Tier 3 ↑' if result.tier3_metrics.profit_factor > result.tier2_metrics.profit_factor else 'Tier 2 ↓'} |")

        return "\n".join(lines)

    def _format_metrics_section(self, metrics, label: str) -> str:
        """Format detailed metrics section."""
        lines = []
        lines.append(f"### {label} Metrics")
        lines.append(f"- **Total Return:** {metrics.total_return:.2f}%")
        lines.append(f"- **Annual Return:** {metrics.annual_return:.2f}%")
        lines.append(f"- **Sharpe Ratio:** {metrics.sharpe_ratio:.4f}")
        lines.append(f"- **Sortino Ratio:** {metrics.sortino_ratio:.4f}")
        lines.append(f"- **Max Drawdown:** {metrics.max_drawdown:.2f}%")
        lines.append(f"- **Calmar Ratio:** {metrics.calmar_ratio:.4f}")
        lines.append(f"- **Volatility:** {metrics.volatility:.2f}%")
        lines.append(f"- **Win Rate:** {metrics.win_rate*100:.1f}%")
        lines.append(f"- **Profit Factor:** {metrics.profit_factor:.2f}")
        lines.append(f"- **Avg Win:** {metrics.avg_win:.4f}%")
        lines.append(f"- **Avg Loss:** {metrics.avg_loss:.4f}%")

        return "\n".join(lines)

    def _create_trades_table(self, trades: List) -> str:
        """Create trades summary table."""
        lines = []
        lines.append("| Date | Entry | Exit | Type | Return | Profit |")
        lines.append("|------|-------|------|------|--------|--------|")

        for trade in trades[:10]:
            lines.append(f"| {trade.date} | ${trade.entry_price:.2f} | ${trade.exit_price:.2f} | "
                        f"{trade.position_type.value.upper()} | {trade.return_pct*100:+.2f}% | "
                        f"${trade.profit:+,.2f} |")

        if len(trades) > 10:
            lines.append(f"| ... | ... | ... | ... | ... | ... |")
            lines.append(f"| *Total {len(trades)} trades* | | | | | |")

        return "\n".join(lines)

    def _metrics_to_dict(self, metrics) -> Dict:
        """Convert metrics to dictionary."""
        return {
            'total_return_pct': float(round(metrics.total_return, self.config.decimal_places)),
            'annual_return_pct': float(round(metrics.annual_return, self.config.decimal_places)),
            'sharpe_ratio': float(round(metrics.sharpe_ratio, self.config.decimal_places)),
            'sortino_ratio': float(round(metrics.sortino_ratio, self.config.decimal_places)),
            'max_drawdown_pct': float(round(metrics.max_drawdown, self.config.decimal_places)),
            'calmar_ratio': float(round(metrics.calmar_ratio, self.config.decimal_places)),
            'volatility_pct': float(round(metrics.volatility, self.config.decimal_places)),
            'win_rate': float(round(metrics.win_rate, 4)),
            'avg_win_pct': float(round(metrics.avg_win, self.config.decimal_places)),
            'avg_loss_pct': float(round(metrics.avg_loss, self.config.decimal_places)),
            'profit_factor': float(round(metrics.profit_factor, self.config.decimal_places)),
            'n_trades': int(metrics.n_trades),
            'n_days': int(metrics.n_days),
        }

    def _trades_to_dicts(self, trades: List) -> List[Dict]:
        """Convert trades to list of dictionaries."""
        return [
            {
                'date': str(t.date),
                'entry_price': float(round(t.entry_price, 2)),
                'exit_price': float(round(t.exit_price, 2)),
                'size': float(t.size),
                'type': str(t.position_type.value),
                'return_pct': float(round(t.return_pct * 100, 2)),
                'profit': float(round(t.profit, 2)),
            }
            for t in trades
        ]

    def _get_recommendation_text(self, recommendation: str) -> str:
        """Get text for recommendation."""
        if recommendation == "GO":
            return "✓ **RECOMMENDATION: GO**\n\nTier 3 demonstrates statistically significant outperformance."
        elif recommendation == "CONDITIONAL_GO":
            return "⚠ **RECOMMENDATION: CONDITIONAL GO**\n\nTier 3 shows improvement but further validation is recommended."
        else:
            return "✗ **RECOMMENDATION: NO GO**\n\nTier 2 baseline should remain in production."
