"""Lexerd Data Pipeline & Batch Processing Orchestrator (LCMV-45).

This package orchestrates all enrichment modules into a unified production pipeline:
- BLS employment enrichment (LCMV-30)
- Census + Zillow market enrichment (LCMV-37)
- SEC + B3 loan matching (LCMV-58)
- Unified 3M Model scoring
- Alert generation and reporting

Main classes:
- DataPipeline: Main orchestrator
- PipelineConfig: Configuration management
- PipelineResult: Pipeline execution results
- EnrichmentMode: Pipeline mode selection (quick/standard/full)
"""

from calibration.pipeline.pipeline import (
    DataPipeline,
    PipelineConfig,
    PipelineResult,
    EnrichmentMode,
    ManagementScorer,
)
from calibration.pipeline.config import (
    load_config,
    load_config_from_yaml,
    load_config_from_json,
    save_config,
    get_default_config,
)
from calibration.pipeline.reporters import (
    CSVReporter,
    HTMLReporter,
    SummaryReporter,
)
from calibration.pipeline.validators import (
    InputValidator,
    OutputValidator,
    DataQualityValidator,
    ThesisValidator,
)

__all__ = [
    'DataPipeline',
    'PipelineConfig',
    'PipelineResult',
    'EnrichmentMode',
    'ManagementScorer',
    'load_config',
    'load_config_from_yaml',
    'load_config_from_json',
    'save_config',
    'get_default_config',
    'CSVReporter',
    'HTMLReporter',
    'SummaryReporter',
    'InputValidator',
    'OutputValidator',
    'DataQualityValidator',
    'ThesisValidator',
]
