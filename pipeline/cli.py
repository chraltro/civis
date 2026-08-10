"""Civis CLI.

  civis fetch     pull all sources to data/raw/
  civis process   build data/processed/civis.json + civis.csv
  civis validate  run the validation suite
  civis refresh   fetch + process + validate, with snapshot
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from . import __version__
from .fetch import DEFAULT_SLEEP_S, fetch_all
from .process import (
    ProcessConfig,
    build_indicator_panel,
    compute_composite,
    compute_domain_z,
    compute_indicator_z,
)
from .process import run as process_run
from .validate import run_all as validate_run

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = REPO_ROOT / "data" / "raw"
DEFAULT_PROCESSED = REPO_ROOT / "data" / "processed"
DEFAULT_SNAPSHOTS = REPO_ROOT / "data" / "snapshots"
DEFAULT_FIXTURES = REPO_ROOT / "tests" / "fixtures"


@click.group()
@click.version_option(__version__)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Civis Index data pipeline."""
    ctx.ensure_object(dict)
    _setup_logging(verbose)


@cli.command("fetch")
@click.option("--raw-dir", type=click.Path(path_type=Path), default=DEFAULT_RAW)
@click.option("--sleep", type=float, default=DEFAULT_SLEEP_S)
def cmd_fetch(raw_dir: Path, sleep: float) -> None:
    """Fetch every indicator source to data/raw/."""
    console.rule("[bold]civis fetch")
    results = fetch_all(raw_dir, sleep_s=sleep)
    console.print(f"Fetched [bold]{len(results)}[/bold] source files into {raw_dir}")


@cli.command("process")
@click.option("--raw-dir", type=click.Path(path_type=Path), default=DEFAULT_RAW)
@click.option("--out-dir", type=click.Path(path_type=Path), default=DEFAULT_PROCESSED)
@click.option("--snapshot/--no-snapshot", default=False)
def cmd_process(raw_dir: Path, out_dir: Path, snapshot: bool) -> None:
    """Build processed JSON + CSV from data/raw/."""
    console.rule("[bold]civis process")
    cfg = ProcessConfig(
        raw_dir=raw_dir,
        out_dir=out_dir,
        snapshot_dir=DEFAULT_SNAPSHOTS if snapshot else None,
    )
    out = process_run(cfg)
    console.print(f"Wrote {out_dir}/civis.json with {len(out['ranked'])} countries ranked")


@cli.command("validate")
@click.option("--raw-dir", type=click.Path(path_type=Path), default=DEFAULT_RAW)
@click.option("--snapshot", "snapshot_path",
              type=click.Path(path_type=Path),
              default=DEFAULT_FIXTURES / "ranking_snapshot.json")
@click.option("--update-snapshot", is_flag=True)
def cmd_validate(raw_dir: Path, snapshot_path: Path, update_snapshot: bool) -> None:
    """Run all validation checks against data in data/raw/."""
    console.rule("[bold]civis validate")
    panel = build_indicator_panel(raw_dir)
    z_indicators = compute_indicator_z(panel)
    z_domains = compute_domain_z(z_indicators)
    composite = compute_composite(z_domains)

    issues = validate_run(
        raw_dir=raw_dir,
        panel=panel,
        z_indicators=z_indicators,
        z_domains=z_domains,
        composite=composite,
        snapshot_path=snapshot_path,
        update_snapshot=update_snapshot,
    )
    errors = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warn"]
    for issue in issues:
        style = "red" if issue.severity == "error" else "yellow"
        console.print(f"[{style}]{issue}[/{style}]")
    console.rule()
    console.print(f"[bold]{len(errors)}[/bold] errors, [bold]{len(warns)}[/bold] warnings")
    if errors:
        sys.exit(1)


@cli.command("refresh")
@click.option("--raw-dir", type=click.Path(path_type=Path), default=DEFAULT_RAW)
@click.option("--out-dir", type=click.Path(path_type=Path), default=DEFAULT_PROCESSED)
@click.option("--update-snapshot", is_flag=True,
              help="Accept any ranking change and update the snapshot fixture.")
def cmd_refresh(raw_dir: Path, out_dir: Path, update_snapshot: bool) -> None:
    """fetch → process (with snapshot) → validate."""
    console.rule("[bold]civis refresh")
    fetch_all(raw_dir)
    cfg = ProcessConfig(
        raw_dir=raw_dir,
        out_dir=out_dir,
        snapshot_dir=DEFAULT_SNAPSHOTS,
    )
    process_run(cfg)
    panel = build_indicator_panel(raw_dir)
    z_indicators = compute_indicator_z(panel)
    z_domains = compute_domain_z(z_indicators)
    composite = compute_composite(z_domains)
    issues = validate_run(
        raw_dir=raw_dir,
        panel=panel,
        z_indicators=z_indicators,
        z_domains=z_domains,
        composite=composite,
        snapshot_path=DEFAULT_FIXTURES / "ranking_snapshot.json",
        update_snapshot=update_snapshot,
    )
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        for i in errors:
            console.print(f"[red]{i}[/red]")
        sys.exit(1)
    console.print("[green]refresh ok[/green]")


if __name__ == "__main__":  # pragma: no cover
    cli()
