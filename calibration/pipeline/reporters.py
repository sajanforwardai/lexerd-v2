"""Report generation and export utilities for pipeline results."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from calibration.models.thesis import ScoreResult
from calibration.pipeline.pipeline import PipelineResult

logger = logging.getLogger(__name__)


class CSVReporter:
    """Export pipeline results to CSV files."""

    @staticmethod
    def export_scored_properties(
        scored: List[ScoreResult],
        output_path: Path,
    ) -> None:
        """
        Export scored properties to CSV.

        Columns:
        - property_id, market_score, model_score, management_score, final_fit_score
        - confidence_grade, fit_rationale, key_strengths, key_weaknesses
        - market_breakdown (JSON), model_breakdown (JSON), management_breakdown (JSON)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            if not scored:
                logger.warning(f"No scored properties to export")
                return

            fieldnames = ['property_id', 'market_score', 'model_score', 'management_score',
                         'final_fit_score', 'confidence_grade', 'fit_rationale',
                         'key_strengths', 'key_weaknesses', 'market_breakdown',
                         'model_breakdown', 'management_breakdown']

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in scored:
                row = {
                    'property_id': result.property_id,
                    'market_score': f"{result.market_score:.2f}",
                    'model_score': f"{result.model_score:.2f}",
                    'management_score': f"{result.management_score:.2f}",
                    'final_fit_score': f"{result.final_fit_score:.2f}",
                    'confidence_grade': result.confidence_grade,
                    'fit_rationale': result.fit_rationale,
                    'key_strengths': ' | '.join(result.key_strengths),
                    'key_weaknesses': ' | '.join(result.key_weaknesses),
                    'market_breakdown': json.dumps(result.market_breakdown),
                    'model_breakdown': json.dumps(result.model_breakdown),
                    'management_breakdown': json.dumps(result.management_breakdown),
                }
                writer.writerow(row)

        logger.info(f"Exported {len(scored)} scored properties to {output_path}")

    @staticmethod
    def export_ranked_opportunities(
        ranked: List[Dict[str, Any]],
        output_path: Path,
        top_n: int = 100,
    ) -> None:
        """
        Export top ranked opportunities to CSV.

        Columns from ScoreResult.to_dict()
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            if not ranked:
                logger.warning(f"No ranked opportunities to export")
                return

            top_ranked = ranked[:top_n]
            fieldnames = top_ranked[0].keys()

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for opp in top_ranked:
                writer.writerow(opp)

        logger.info(f"Exported {len(top_ranked)} ranked opportunities to {output_path}")

    @staticmethod
    def export_alerts(
        maturity_signals: List[Dict[str, Any]],
        refinance_opportunities: List[Dict[str, Any]],
        output_path: Path,
    ) -> None:
        """
        Export alerts (maturity signals + refinance opportunities) to CSV.

        Columns: signal_type, property_id, property_name, alert_level, ...
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        all_alerts = maturity_signals + refinance_opportunities

        with open(output_path, 'w', newline='') as f:
            if not all_alerts:
                logger.warning(f"No alerts to export")
                return

            # Collect all possible fieldnames from all alerts
            fieldnames = set()
            for alert in all_alerts:
                fieldnames.update(alert.keys())
            fieldnames = sorted(list(fieldnames))

            writer = csv.DictWriter(f, fieldnames=fieldnames, restval='')
            writer.writeheader()

            for alert in all_alerts:
                writer.writerow(alert)

        logger.info(f"Exported {len(all_alerts)} alerts to {output_path}")


class HTMLReporter:
    """Export pipeline results to HTML."""

    @staticmethod
    def export_opportunities_dashboard(
        ranked: List[Dict[str, Any]],
        maturity_signals: List[Dict[str, Any]],
        refinance_opportunities: List[Dict[str, Any]],
        output_path: Path,
        top_n: int = 100,
    ) -> None:
        """
        Generate HTML dashboard with top opportunities and alerts.

        Output: An interactive HTML dashboard with:
        - Top ranked opportunities (table)
        - Maturity signals (highlight rows)
        - Refinance opportunities (highlight rows)
        - Summary statistics
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        top_ranked = ranked[:top_n]

        # Build HTML
        html = _build_opportunities_html(top_ranked, maturity_signals, refinance_opportunities)

        with open(output_path, 'w') as f:
            f.write(html)

        logger.info(f"Exported opportunities dashboard to {output_path}")

    @staticmethod
    def export_summary_report(
        result: PipelineResult,
        output_path: Path,
    ) -> None:
        """
        Generate HTML summary report.

        Includes:
        - Execution metrics (input count, scoring coverage, execution time)
        - Data lineage (which sources contributed)
        - Error summary
        - Top opportunities
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html = _build_summary_html(result)

        with open(output_path, 'w') as f:
            f.write(html)

        logger.info(f"Exported summary report to {output_path}")


class SummaryReporter:
    """Export pipeline execution summary and metrics."""

    @staticmethod
    def export_execution_summary(
        result: PipelineResult,
        output_path: Path,
    ) -> None:
        """
        Export execution summary as JSON.

        Contents:
        - Status, timestamp, execution_time_seconds
        - input_count, output_count (scored properties)
        - Coverage stats (% enriched by source)
        - Error summary
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            'status': result.status,
            'timestamp': result.timestamp.isoformat(),
            'execution_time_seconds': result.execution_time_seconds,
            'input_count': result.input_count,
            'output_counts': {
                'scored_properties': len(result.scored_properties),
                'ranked_opportunities': len(result.ranked_opportunities),
                'maturity_signals': len(result.maturity_signals),
                'refinance_opportunities': len(result.refinance_opportunities),
            },
            'coverage_stats': result.coverage_stats,
            'error_summary': result.error_summary,
            'enrichment_results': result.enrichment_results,
        }

        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Exported execution summary to {output_path}")


# HTML generation helpers

def _build_opportunities_html(
    ranked: List[Dict[str, Any]],
    maturity_signals: List[Dict[str, Any]],
    refinance_opportunities: List[Dict[str, Any]],
) -> str:
    """Build HTML table of opportunities with highlights."""
    maturity_ids = {s['property_id'] for s in maturity_signals}
    refinance_ids = {o['property_id'] for o in refinance_opportunities}

    # Build timestamp outside of format string to avoid brace issues
    timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Lexerd Deal Engine - Opportunities Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background: #007bff; color: white; padding: 12px; text-align: left; font-weight: bold; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f9f9f9; }}
        .maturity {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
        .refinance {{ background: #d1ecf1; border-left: 4px solid #17a2b8; }}
        .score-a {{ color: #28a745; font-weight: bold; }}
        .score-b {{ color: #ffc107; font-weight: bold; }}
        .score-c {{ color: #fd7e14; font-weight: bold; }}
        .score-d {{ color: #dc3545; font-weight: bold; }}
        .stats {{ background: #e7f3ff; padding: 15px; border-radius: 4px; margin: 20px 0; }}
        .stat-item {{ display: inline-block; margin-right: 30px; }}
        .stat-label {{ font-weight: bold; color: #007bff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Lexerd Deal Engine - Opportunities Dashboard</h1>
        <p>Generated: {timestamp_str}</p>

        <div class="stats">
            <div class="stat-item"><span class="stat-label">Total Opportunities:</span> {len(ranked)}</div>
            <div class="stat-item"><span class="stat-label">Maturity Signals:</span> {len(maturity_signals)}</div>
            <div class="stat-item"><span class="stat-label">Refinance Signals:</span> {len(refinance_opportunities)}</div>
        </div>

        <h2>Top Opportunities</h2>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Property ID</th>
                    <th>Market Score</th>
                    <th>Model Score</th>
                    <th>Management Score</th>
                    <th>Final Score</th>
                    <th>Grade</th>
                </tr>
            </thead>
            <tbody>
"""

    for idx, opp in enumerate(ranked, 1):
        prop_id = opp.get('property_id', '')
        row_class = ''
        if prop_id in maturity_ids:
            row_class = 'class="maturity"'
        elif prop_id in refinance_ids:
            row_class = 'class="refinance"'

        grade = opp.get('confidence_grade', 'D')
        grade_class = f"score-{grade.lower()}"

        html += f"""                <tr {row_class}>
                    <td>{idx}</td>
                    <td>{prop_id}</td>
                    <td>{opp.get('market_score', 0):.1f}</td>
                    <td>{opp.get('model_score', 0):.1f}</td>
                    <td>{opp.get('management_score', 0):.1f}</td>
                    <td><strong>{opp.get('final_fit_score', 0):.1f}</strong></td>
                    <td><span class="{grade_class}">{grade}</span></td>
                </tr>
"""

    html += """            </tbody>
        </table>

        <p style="margin-top: 30px; font-size: 12px; color: #999;">
            <strong>Legend:</strong>
            <span style="background: #fff3cd; padding: 3px 8px; border-radius: 3px;">Maturity Signal</span>
            <span style="background: #d1ecf1; padding: 3px 8px; border-radius: 3px; margin-left: 10px;">Refinance Signal</span>
        </p>
    </div>
</body>
</html>
"""

    return html


def _build_summary_html(result: PipelineResult) -> str:
    """Build HTML summary report."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Lexerd Data Pipeline - Execution Summary</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .status {{ padding: 10px 15px; border-radius: 4px; font-weight: bold; }}
        .status.success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .status.error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        .metric {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-left: 4px solid #007bff; }}
        .metric-label {{ font-weight: bold; color: #333; }}
        .metric-value {{ font-size: 18px; color: #007bff; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f0f0f0; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Lexerd Data Pipeline - Execution Summary</h1>

        <div class="status {result.status}">
            Status: {result.status.upper()}
        </div>

        <div class="metric">
            <div class="metric-label">Execution Time</div>
            <div class="metric-value">{result.execution_time_seconds:.2f} seconds</div>
        </div>

        <div class="metric">
            <div class="metric-label">Input Properties</div>
            <div class="metric-value">{result.input_count}</div>
        </div>

        <div class="metric">
            <div class="metric-label">Scored Properties</div>
            <div class="metric-value">{len(result.scored_properties)}</div>
        </div>

        <div class="metric">
            <div class="metric-label">Top Opportunities</div>
            <div class="metric-value">{len(result.ranked_opportunities)}</div>
        </div>

        <div class="metric">
            <div class="metric-label">Maturity Signals</div>
            <div class="metric-value">{len(result.maturity_signals)}</div>
        </div>

        <div class="metric">
            <div class="metric-label">Refinance Opportunities</div>
            <div class="metric-value">{len(result.refinance_opportunities)}</div>
        </div>

        <h2>Coverage Statistics</h2>
        <table>
            <thead>
                <tr>
                    <th>Data Source</th>
                    <th>Coverage %</th>
                </tr>
            </thead>
            <tbody>
"""

    for source, coverage in result.coverage_stats.items():
        html += f"                <tr><td>{source}</td><td>{coverage:.1f}%</td></tr>\n"

    html += """            </tbody>
        </table>

        <h2>Error Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>Error Type</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>
"""

    if result.error_summary:
        for error_type, count in result.error_summary.items():
            html += f"                <tr><td>{error_type}</td><td>{count}</td></tr>\n"
    else:
        html += "                <tr><td colspan='2'>No errors</td></tr>\n"

    html += f"""            </tbody>
        </table>

        <p style="margin-top: 30px; font-size: 12px; color: #999;">
            Generated: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""

    return html
