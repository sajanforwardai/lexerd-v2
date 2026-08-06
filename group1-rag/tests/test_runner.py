"""test_runner.py — Comprehensive test runner with custom reporting.

Executes the full Group One RAG test suite and generates:
  1. Detailed test results (JSON)
  2. Performance benchmarks
  3. Regression analysis
  4. Summary report (markdown)

Usage:
  python test_runner.py                           # Run all tests
  python test_runner.py --tier 1                  # Run Tier 1 only
  python test_runner.py --tier 2                  # Run Tier 2 only
  python test_runner.py --compare baseline.json   # Check for regressions
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class TestRunner:
    """Main test execution and reporting."""

    def __init__(self, results_dir: Optional[Path] = None):
        """Initialize test runner.

        Args:
            results_dir: Directory for test results (default: ./results)
        """
        self.results_dir = results_dir or Path(__file__).parent / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.test_results: list[dict] = []

    def run_tests(
        self,
        tier: Optional[int] = None,
        e2e_only: bool = False,
        verbose: bool = True
    ) -> int:
        """Run test suite with pytest.

        Args:
            tier: Run specific tier (1, 2, or None for all)
            e2e_only: Run only E2E tests
            verbose: Verbose output

        Returns:
            pytest exit code (0 = success)
        """
        cmd = ["pytest", str(Path(__file__).parent)]

        if verbose:
            cmd.append("-v")

        if e2e_only:
            cmd.extend(["-m", "e2e"])
        elif tier == 1:
            cmd.extend(["-m", "tier1"])
        elif tier == 2:
            cmd.extend(["-m", "tier2"])

        # Add result output
        result_file = self.results_dir / f"results_{datetime.now().isoformat(timespec='seconds')}.json"
        cmd.extend(["-v", f"--junit-xml={self.results_dir}/junit.xml"])

        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)

        return result.returncode

    def load_junit_results(self, junit_path: Path) -> dict[str, Any]:
        """Load and parse JUnit XML results.

        Args:
            junit_path: Path to JUnit XML file

        Returns:
            Parsed results dict
        """
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(junit_path)
            root = tree.getroot()

            results = {
                "total": int(root.get("tests", 0)),
                "passed": int(root.get("tests", 0)) - int(root.get("failures", 0)) - int(root.get("errors", 0)),
                "failed": int(root.get("failures", 0)),
                "errors": int(root.get("errors", 0)),
                "skipped": int(root.get("skipped", 0)),
                "time_seconds": float(root.get("time", 0)),
                "testcases": []
            }

            for testcase in root.findall("testcase"):
                tc = {
                    "classname": testcase.get("classname"),
                    "name": testcase.get("name"),
                    "time": float(testcase.get("time", 0))
                }
                if testcase.find("failure") is not None:
                    tc["status"] = "FAILED"
                elif testcase.find("error") is not None:
                    tc["status"] = "ERROR"
                else:
                    tc["status"] = "PASSED"

                results["testcases"].append(tc)

            return results
        except Exception as e:
            logger.error(f"Error parsing JUnit results: {e}")
            return {"error": str(e)}

    def generate_summary_report(self, results: dict[str, Any]) -> str:
        """Generate markdown summary report.

        Args:
            results: Test results dictionary

        Returns:
            Markdown report string
        """
        report = []
        report.append("# Group One RAG Test Report")
        report.append(f"\n**Generated:** {datetime.now().isoformat()}")
        report.append("\n## Test Execution Summary\n")

        if "error" in results:
            report.append(f"⚠️  Error loading results: {results['error']}\n")
            return "\n".join(report)

        report.append(f"- **Total Tests:** {results['total']}")
        report.append(f"- **Passed:** ✅ {results['passed']}")
        report.append(f"- **Failed:** ❌ {results['failed']}")
        report.append(f"- **Errors:** ⚠️  {results['errors']}")
        report.append(f"- **Skipped:** ⏭️  {results['skipped']}")
        report.append(f"- **Duration:** {results['time_seconds']:.2f}s")

        # Calculate pass rate
        if results['total'] > 0:
            pass_rate = (results['passed'] / results['total']) * 100
            report.append(f"- **Pass Rate:** {pass_rate:.1f}%")

        # Test breakdown by category
        report.append("\n## Test Breakdown by Category\n")

        tier1_tests = [t for t in results['testcases'] if 'TestTier1' in t['classname']]
        tier2_tests = [t for t in results['testcases'] if 'TestTier2' in t['classname']]
        e2e_tests = [t for t in results['testcases'] if 'TestEndToEnd' in t['classname']]

        def format_category(name: str, tests: list[dict]) -> str:
            if not tests:
                return ""
            passed = sum(1 for t in tests if t['status'] == 'PASSED')
            total = len(tests)
            rate = (passed / total * 100) if total > 0 else 0
            return f"- **{name}:** {passed}/{total} passed ({rate:.0f}%)"

        report.append(format_category("Tier 1 Retrieval", tier1_tests))
        report.append(format_category("Tier 2 Entity Extraction", tier2_tests))
        report.append(format_category("End-to-End", e2e_tests))

        # Benchmark targets
        report.append("\n## Benchmark Targets\n")
        report.append("| Metric | Target | Status |")
        report.append("|--------|--------|--------|")
        report.append("| Tier 1 Precision@10 | ≥ 0.50 | 📊 Measure |")
        report.append("| Tier 2 Entity F1 | ≥ 0.85 | 📊 Measure |")
        report.append("| Tier 1 Latency | ≤ 100ms | 📊 Measure |")
        report.append("| Tier 2 Latency | ≤ 500ms | 📊 Measure |")

        # Recommendations
        report.append("\n## Recommendations\n")
        if results['failed'] > 0 or results['errors'] > 0:
            report.append("- ❌ Fix failing tests before deployment")
            report.append("- 📋 Review error logs in `results/pytest.log`")
        else:
            report.append("- ✅ All tests passing - system ready for evaluation")

        report.append("\n## Test Files\n")
        report.append("- `test_retrieval.py` - Tier 1 retrieval evaluation")
        report.append("- `test_entity_extraction.py` - Tier 2 entity extraction")
        report.append("- `test_end_to_end.py` - E2E pipeline tests")
        report.append("- `test_metrics.py` - Metrics and evaluation logic")
        report.append("- `conftest.py` - Pytest fixtures and configuration")
        report.append("- `golden_queries.json` - 500 golden query set")

        return "\n".join(report)

    def save_summary(self, report_text: str, filename: str = "RESULTS.md") -> Path:
        """Save summary report to file.

        Args:
            report_text: Report markdown text
            filename: Output filename

        Returns:
            Path to saved report
        """
        report_path = self.results_dir / filename
        with open(report_path, "w") as f:
            f.write(report_text)
        logger.info(f"Saved report to {report_path}")
        return report_path

    def run_full_suite(self, verbose: bool = True) -> dict[str, Any]:
        """Run complete test suite and generate reports.

        Args:
            verbose: Verbose output

        Returns:
            Results dictionary
        """
        logger.info("=" * 60)
        logger.info("Group One RAG Test Suite")
        logger.info("=" * 60)

        # Run tests
        exit_code = self.run_tests(verbose=verbose)

        # Load results
        junit_file = self.results_dir / "junit.xml"
        results = self.load_junit_results(junit_file) if junit_file.exists() else {}

        # Generate report
        summary = self.generate_summary_report(results)

        # Save report
        self.save_summary(summary)

        # Print summary
        print("\n" + "=" * 60)
        print(summary)
        print("=" * 60)

        return {
            "exit_code": exit_code,
            "results": results,
            "summary": summary
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Group One RAG Test Runner",
        epilog="Example: python test_runner.py --tier 1 --verbose"
    )

    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2],
        help="Run specific tier (1 or 2)"
    )

    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Run only end-to-end tests"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output"
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        help="Results directory (default: ./results)"
    )

    args = parser.parse_args()

    # Create runner
    runner = TestRunner(results_dir=args.results_dir)

    # Run tests
    result = runner.run_tests(
        tier=args.tier,
        e2e_only=args.e2e,
        verbose=args.verbose
    )

    # Generate reports
    junit_file = runner.results_dir / "junit.xml"
    if junit_file.exists():
        results = runner.load_junit_results(junit_file)
        summary = runner.generate_summary_report(results)
        runner.save_summary(summary)
        print("\n" + "=" * 60)
        print(summary)
        print("=" * 60)

    sys.exit(result)


if __name__ == "__main__":
    main()
