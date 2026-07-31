"""Pipeline configuration management with YAML + CLI support."""

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from calibration.models.thesis import ThesisConfig
from calibration.pipeline.pipeline import EnrichmentMode, PipelineConfig

logger = logging.getLogger(__name__)


def load_config_from_yaml(config_path: Path) -> PipelineConfig:
    """
    Load pipeline configuration from YAML file.

    YAML structure:
    ```yaml
    enrichment_mode: standard
    bls_api_key: ${BLS_API_KEY}  # environment variable
    thesis:
        target_markets: [GA, FL, AL]
        min_employment_growth_yoy: 0.02
        ...
    output_settings:
        output_dir: ./results
        export_csv: true
        export_html: true
        export_pdf: false
    ```

    Args:
        config_path: Path to YAML configuration file

    Returns:
        PipelineConfig instance

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        raise ValueError("Config file is empty")

    # Parse enrichment mode
    enrichment_mode = EnrichmentMode(config_dict.get('enrichment_mode', 'standard'))

    # Parse thesis config
    thesis_dict = config_dict.get('thesis', {})
    thesis = ThesisConfig(**thesis_dict) if thesis_dict else ThesisConfig()

    # Parse output settings
    output_dict = config_dict.get('output_settings', {})
    output_dir = Path(output_dict.get('output_dir', './results'))

    # Create PipelineConfig
    pipeline_config = PipelineConfig(
        enrichment_mode=enrichment_mode,
        bls_api_key=config_dict.get('bls_api_key'),
        sec_cache_dir=Path(config_dict['sec_cache_dir']) if config_dict.get('sec_cache_dir') else None,
        loan_tape_path=Path(config_dict['loan_tape_path']) if config_dict.get('loan_tape_path') else None,
        skip_enrichment=config_dict.get('skip_enrichment', False),
        skip_validation=config_dict.get('skip_validation', False),
        dry_run=config_dict.get('dry_run', False),
        thesis=thesis,
        output_dir=output_dir,
        export_csv=output_dict.get('export_csv', True),
        export_html=output_dict.get('export_html', True),
        export_pdf=output_dict.get('export_pdf', False),
        batch_size=config_dict.get('batch_size', 100),
        max_workers=config_dict.get('max_workers', 4),
        timeout_seconds=config_dict.get('timeout_seconds', 300),
    )

    logger.info(f"Loaded configuration from {config_path}")
    return pipeline_config


def load_config_from_json(config_path: Path) -> PipelineConfig:
    """Load pipeline configuration from JSON file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config_dict = json.load(f)

    # Same parsing logic as YAML
    enrichment_mode = EnrichmentMode(config_dict.get('enrichment_mode', 'standard'))
    thesis_dict = config_dict.get('thesis', {})
    thesis = ThesisConfig(**thesis_dict) if thesis_dict else ThesisConfig()
    output_dict = config_dict.get('output_settings', {})
    output_dir = Path(output_dict.get('output_dir', './results'))

    pipeline_config = PipelineConfig(
        enrichment_mode=enrichment_mode,
        bls_api_key=config_dict.get('bls_api_key'),
        sec_cache_dir=Path(config_dict['sec_cache_dir']) if config_dict.get('sec_cache_dir') else None,
        loan_tape_path=Path(config_dict['loan_tape_path']) if config_dict.get('loan_tape_path') else None,
        skip_enrichment=config_dict.get('skip_enrichment', False),
        skip_validation=config_dict.get('skip_validation', False),
        dry_run=config_dict.get('dry_run', False),
        thesis=thesis,
        output_dir=output_dir,
        export_csv=output_dict.get('export_csv', True),
        export_html=output_dict.get('export_html', True),
        export_pdf=output_dict.get('export_pdf', False),
        batch_size=config_dict.get('batch_size', 100),
        max_workers=config_dict.get('max_workers', 4),
        timeout_seconds=config_dict.get('timeout_seconds', 300),
    )

    logger.info(f"Loaded configuration from {config_path}")
    return pipeline_config


def load_config(
    config_path: Optional[Path] = None,
    enrichment_mode: Optional[str] = None,
    output_dir: Optional[Path] = None,
    bls_api_key: Optional[str] = None,
) -> PipelineConfig:
    """
    Load pipeline configuration with CLI overrides.

    Priority order:
    1. CLI arguments (highest)
    2. Config file
    3. Environment variables
    4. Defaults (lowest)

    Args:
        config_path: Path to config file (YAML or JSON)
        enrichment_mode: Override enrichment mode (quick/standard/full)
        output_dir: Override output directory
        bls_api_key: Override BLS API key

    Returns:
        PipelineConfig instance
    """
    # Load from file if provided
    if config_path:
        if config_path.suffix == '.yaml' or config_path.suffix == '.yml':
            config = load_config_from_yaml(config_path)
        elif config_path.suffix == '.json':
            config = load_config_from_json(config_path)
        else:
            raise ValueError(f"Unsupported config format: {config_path.suffix}")
    else:
        # Use defaults
        config = PipelineConfig()

    # Apply CLI overrides
    if enrichment_mode:
        config.enrichment_mode = EnrichmentMode(enrichment_mode)
    if output_dir:
        config.output_dir = output_dir
    if bls_api_key:
        config.bls_api_key = bls_api_key

    return config


def save_config(config: PipelineConfig, output_path: Path, format: str = 'yaml') -> None:
    """
    Save pipeline configuration to file.

    Args:
        config: PipelineConfig instance
        output_path: Path to save configuration
        format: 'yaml' or 'json'

    Raises:
        ValueError: If format not supported
    """
    # Convert to dict
    config_dict = {
        'enrichment_mode': config.enrichment_mode.value,
        'bls_api_key': config.bls_api_key,
        'sec_cache_dir': str(config.sec_cache_dir) if config.sec_cache_dir else None,
        'loan_tape_path': str(config.loan_tape_path) if config.loan_tape_path else None,
        'skip_enrichment': config.skip_enrichment,
        'skip_validation': config.skip_validation,
        'dry_run': config.dry_run,
        'thesis': config.thesis.to_dict(),
        'output_settings': {
            'output_dir': str(config.output_dir),
            'export_csv': config.export_csv,
            'export_html': config.export_html,
            'export_pdf': config.export_pdf,
        },
        'batch_size': config.batch_size,
        'max_workers': config.max_workers,
        'timeout_seconds': config.timeout_seconds,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == 'yaml':
        with open(output_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
    elif format == 'json':
        with open(output_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
    else:
        raise ValueError(f"Unsupported format: {format}")

    logger.info(f"Saved configuration to {output_path}")


def get_default_config() -> PipelineConfig:
    """Get default pipeline configuration."""
    return PipelineConfig(
        enrichment_mode=EnrichmentMode.STANDARD,
        thesis=ThesisConfig(),
        output_dir=Path.cwd() / "results",
    )
