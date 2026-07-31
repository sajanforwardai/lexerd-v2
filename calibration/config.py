"""Configuration loading and management for thesis parameters."""

import json
from pathlib import Path
from typing import Dict, Any

from models.thesis import ThesisConfig


def load_config(config_path: Path = None) -> ThesisConfig:
    """Load thesis configuration from JSON file."""
    if config_path is None:
        config_path = Path(__file__).parent / "config" / "lexerd_thesis.json"

    if not config_path.exists():
        # Return default config
        return ThesisConfig()

    with open(config_path, 'r') as f:
        config_dict = json.load(f)

    return ThesisConfig(**config_dict)


def save_config(thesis: ThesisConfig, config_path: Path = None) -> None:
    """Save thesis configuration to JSON file."""
    if config_path is None:
        config_path = Path(__file__).parent / "config" / "lexerd_thesis.json"

    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(thesis.to_dict(), f, indent=2)


def get_default_config() -> ThesisConfig:
    """Return Lexerd's default thesis configuration."""
    return ThesisConfig(
        target_markets=['GA', 'FL', 'AL', 'SC', 'NC', 'TX', 'KS'],
        max_population=1_000_000,
        min_employment_growth_yoy=0.02,
        employment_anchor_types=['military', 'medical', 'university', 'manufacturing'],
        min_population_growth_yoy=0.015,
        min_cap_rate_spread_bps=200,
        min_equity=2_000_000,
        max_equity=20_000_000,
        min_capital=10_000_000,
        max_capital=100_000_000,
        max_acq_price=50_000_000,
        min_units=70,
        max_units=300,
        min_occupancy=0.80,
        max_occupancy=0.95,
        min_expense_ratio_above_benchmark=0.05,
        require_third_party_management=True,
        market_weight=0.30,
        model_weight=0.40,
        management_weight=0.30,
        target_irr_pct=12.0,
    )
