"""Command-line interface for Lexerd data pipeline orchestrator."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from calibration.pipeline.config import load_config, save_config
from calibration.pipeline.pipeline import DataPipeline, EnrichmentMode, PipelineConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli():
    """Lexerd Data Pipeline Orchestrator (LCMV-45)."""
    pass


@cli.command()
@click.argument('input_csv', type=click.Path(exists=True), required=True)
@click.option(
    '--config',
    type=click.Path(exists=True),
    help='Path to configuration file (YAML or JSON)'
)
@click.option(
    '--mode',
    type=click.Choice(['quick', 'standard', 'full']),
    default='standard',
    help='Enrichment mode: quick (BLS only) | standard (BLS+SEC) | full (all sources)'
)
@click.option(
    '--output-dir',
    type=click.Path(),
    default='./results',
    help='Output directory for results'
)
@click.option(
    '--bls-api-key',
    envvar='BLS_API_KEY',
    help='BLS API key (or set BLS_API_KEY env var)'
)
@click.option(
    '--sec-cache-dir',
    type=click.Path(),
    help='Cache directory for SEC Edgar data'
)
@click.option(
    '--skip-enrichment',
    is_flag=True,
    help='Skip data enrichment step'
)
@click.option(
    '--skip-validation',
    is_flag=True,
    help='Skip input validation step'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Run pipeline without writing output files'
)
@click.option(
    '--export-csv',
    is_flag=True,
    default=True,
    help='Export results as CSV'
)
@click.option(
    '--export-html',
    is_flag=True,
    default=True,
    help='Export results as HTML'
)
@click.option(
    '--export-pdf',
    is_flag=True,
    default=False,
    help='Export results as PDF'
)
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    help='Verbose logging'
)
def run(
    input_csv: str,
    config: Optional[str],
    mode: str,
    output_dir: str,
    bls_api_key: Optional[str],
    sec_cache_dir: Optional[str],
    skip_enrichment: bool,
    skip_validation: bool,
    dry_run: bool,
    export_csv: bool,
    export_html: bool,
    export_pdf: bool,
    verbose: bool,
):
    """
    Run the Lexerd data pipeline.

    This orchestrates all enrichment modules to identify top opportunities:

    1. Load input CSV with property data
    2. Enrich with BLS employment, SEC loan data, Census, Zillow
    3. Score using 3M Model (Market/Model/Management)
    4. Rank opportunities and identify alerts
    5. Export results (CSV, HTML, PDF)

    Example:

        # Run with standard enrichment
        lexerd-pipeline run properties.csv --mode standard --output-dir ./results

        # Run with full configuration
        lexerd-pipeline run properties.csv --config pipeline_config.yaml

        # Quick mode (BLS only)
        lexerd-pipeline run properties.csv --mode quick --dry-run
    """
    input_csv_path = Path(input_csv)
    output_dir_path = Path(output_dir)

    # Set up logging
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load configuration
        if config:
            config_path = Path(config)
            pipeline_config = load_config(
                config_path=config_path,
                enrichment_mode=mode,
                output_dir=output_dir_path,
                bls_api_key=bls_api_key,
            )
        else:
            pipeline_config = load_config(
                enrichment_mode=mode,
                output_dir=output_dir_path,
                bls_api_key=bls_api_key,
            )

        # Apply command-line overrides
        pipeline_config.skip_enrichment = skip_enrichment
        pipeline_config.skip_validation = skip_validation
        pipeline_config.dry_run = dry_run
        pipeline_config.export_csv = export_csv
        pipeline_config.export_html = export_html
        pipeline_config.export_pdf = export_pdf

        if sec_cache_dir:
            pipeline_config.sec_cache_dir = Path(sec_cache_dir)

        # Validate input
        if not input_csv_path.exists():
            click.echo(f"Error: Input file not found: {input_csv_path}", err=True)
            sys.exit(1)

        # Run pipeline
        click.echo(f"Running Lexerd Data Pipeline (mode: {mode})")
        click.echo(f"Input: {input_csv_path}")
        click.echo(f"Output: {output_dir_path}")

        pipeline = DataPipeline(pipeline_config)
        result = pipeline.run(input_csv_path)

        # Display results
        if result.status == "success":
            click.echo("\n" + "=" * 80)
            click.echo("PIPELINE COMPLETE (SUCCESS)")
            click.echo("=" * 80)
            click.echo(f"Input properties: {result.input_count}")
            click.echo(f"Scored properties: {len(result.scored_properties)}")
            click.echo(f"Top opportunities: {len(result.ranked_opportunities)}")
            click.echo(f"Maturity signals: {len(result.maturity_signals)}")
            click.echo(f"Refinance opportunities: {len(result.refinance_opportunities)}")
            click.echo(f"Execution time: {result.execution_time_seconds:.2f}s")
            click.echo(f"Output directory: {output_dir_path}")
            sys.exit(0)
        else:
            click.echo("\n" + "=" * 80, err=True)
            click.echo("PIPELINE FAILED", err=True)
            click.echo("=" * 80, err=True)
            click.echo(f"Error summary: {result.error_summary}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument('output_path', type=click.Path(), required=True)
@click.option(
    '--format',
    type=click.Choice(['yaml', 'json']),
    default='yaml',
    help='Configuration format'
)
def init_config(output_path: str, format: str):
    """
    Initialize a configuration file with default settings.

    Example:

        lexerd-pipeline init-config pipeline_config.yaml
    """
    output_path = Path(output_path)

    # Check if file exists
    if output_path.exists():
        if not click.confirm(f"File exists: {output_path}. Overwrite?"):
            click.echo("Cancelled")
            return

    try:
        from calibration.pipeline.config import get_default_config
        config = get_default_config()
        save_config(config, output_path, format=format)
        click.echo(f"Created configuration: {output_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('config_path', type=click.Path(exists=True), required=True)
def validate_config(config_path: str):
    """
    Validate a configuration file.

    Example:

        lexerd-pipeline validate-config pipeline_config.yaml
    """
    config_path = Path(config_path)

    try:
        from calibration.pipeline.config import load_config
        config = load_config(config_path=config_path)
        click.echo("Configuration is valid")
        click.echo(f"  Enrichment mode: {config.enrichment_mode.value}")
        click.echo(f"  Output directory: {config.output_dir}")
        click.echo(f"  Export CSV: {config.export_csv}")
        click.echo(f"  Export HTML: {config.export_html}")
        click.echo(f"  Export PDF: {config.export_pdf}")
    except Exception as e:
        click.echo(f"Configuration is INVALID: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_csv', type=click.Path(exists=True), required=True)
def validate_input(input_csv: str):
    """
    Validate input CSV file.

    Example:

        lexerd-pipeline validate-input properties.csv
    """
    input_csv_path = Path(input_csv)

    try:
        from calibration.pipeline.pipeline import DataPipeline, PipelineConfig

        config = PipelineConfig(skip_enrichment=True, skip_validation=False)
        pipeline = DataPipeline(config)

        properties = pipeline._load_properties(input_csv_path)
        validation = pipeline._validate_input(properties)

        click.echo(f"Validation results:")
        click.echo(f"  Total properties: {validation['total_count']}")
        click.echo(f"  Valid properties: {validation['valid_count']}")
        click.echo(f"  Invalid properties: {validation['total_count'] - validation['valid_count']}")

        # Show first few errors
        errors_shown = 0
        for prop_id, details in validation['details'].items():
            if not details['valid'] and errors_shown < 5:
                click.echo(f"  {prop_id}: {', '.join(details['errors'])}")
                errors_shown += 1

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
