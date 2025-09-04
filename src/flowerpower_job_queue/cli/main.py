"""CLI commands for flowerpower-job-queue."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click

from ..core.job import Job, JobStatus
from ..core.manager import JobQueueManager


@click.group()
@click.pass_context
def queue(ctx: click.Context) -> None:
    """Manage FlowerPower job queues."""
    # Ensure we have a context object
    ctx.ensure_object(dict)
    
    # Try to find the project root
    ctx.obj["project_root"] = find_project_root()


@queue.command()
@click.argument("pipeline_name")
@click.option(
    "--inputs",
    help="Input variables as JSON string",
    default="{}",
)
@click.option(
    "--final-vars",
    help="Comma-separated list of final variables",
    multiple=True,
)
@click.option(
    "--config",
    help="Additional configuration as JSON string",
    default="{}",
)
@click.option(
    "--executor",
    help="Hamilton executor to use",
)
@click.option(
    "--queue",
    "queue_name",
    help="Queue to enqueue the job in",
    default="default",
)
@click.option(
    "--priority",
    type=int,
    help="Job priority (higher = more priority)",
    default=0,
)
@click.option(
    "--timeout",
    type=int,
    help="Job timeout in seconds",
)
@click.option(
    "--max-retries",
    type=int,
    help="Maximum number of retries",
    default=3,
)
@click.option(
    "--retry-delay",
    type=float,
    help="Delay between retries in seconds",
    default=10.0,
)
@click.option(
    "--log-level",
    help="Logging level",
    default="INFO",
)
@click.pass_context
def enqueue(
    ctx: click.Context,
    pipeline_name: str,
    inputs: str,
    final_vars: tuple[str, ...],
    config: str,
    executor: Optional[str],
    queue_name: str,
    priority: int,
    timeout: Optional[int],
    max_retries: int,
    retry_delay: float,
    log_level: str,
) -> None:
    """Enqueue a pipeline for execution."""
    project_root = ctx.obj["project_root"]
    if not project_root:
        click.echo("Error: Could not find project root", err=True)
        sys.exit(1)
    
    # Parse JSON inputs
    try:
        inputs_dict = json.loads(inputs)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing inputs JSON: {e}", err=True)
        sys.exit(1)
    
    try:
        config_dict = json.loads(config)
    except json.JSONDecodeError as e:
        click.echo(f"Error parsing config JSON: {e}", err=True)
        sys.exit(1)
    
    # Parse final vars
    final_vars_list = None
    if final_vars:
        final_vars_list = [var.strip() for var in ",".join(final_vars).split(",")]
    
    # Load configuration
    job_queue_config = load_job_queue_config(project_root)
    
    # Create manager
    manager = JobQueueManager(job_queue_config)
    
    # Create and enqueue job
    job = manager.create_job(
        pipeline_name=pipeline_name,
        base_dir=str(project_root),
        inputs=inputs_dict,
        final_vars=final_vars_list,
        config=config_dict,
        executor=executor,
        queue_name=queue_name,
        priority=priority,
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        log_level=log_level,
    )
    
    try:
        enqueued_job = manager.enqueue(job)
        click.echo(f"Successfully enqueued job: {enqueued_job.job_id}")
        click.echo(f"Pipeline: {enqueued_job.pipeline_name}")
        click.echo(f"Queue: {enqueued_job.queue_name}")
        click.echo(f"Status: {enqueued_job.status.value}")
    except Exception as e:
        click.echo(f"Error enqueuing job: {e}", err=True)
        sys.exit(1)


@queue.command()
@click.argument("queues", nargs=-1, required=True)
@click.option(
    "--name",
    help="Worker name",
)
@click.option(
    "--burst",
    is_flag=True,
    help="Run in burst mode (exit when no jobs)",
)
@click.option(
    "--worker-ttl",
    type=int,
    help="Worker time to live in seconds",
    default=420,
)
@click.option(
    "--result-ttl",
    type=int,
    help="Result time to live in seconds",
    default=500,
)
@click.pass_context
def worker(
    ctx: click.Context,
    queues: tuple[str, ...],
    name: Optional[str],
    burst: bool,
    worker_ttl: int,
    result_ttl: int,
) -> None:
    """Start a worker process."""
    project_root = ctx.obj["project_root"]
    if not project_root:
        click.echo("Error: Could not find project root", err=True)
        sys.exit(1)
    
    # Load configuration
    job_queue_config = load_job_queue_config(project_root)
    
    # Create manager
    manager = JobQueueManager(job_queue_config)
    
    # Start worker
    try:
        click.echo(f"Starting worker for queues: {', '.join(queues)}")
        manager.start_worker(
            queues=list(queues),
            name=name,
            burst=burst,
            worker_ttl=worker_ttl,
            result_ttl=result_ttl,
        )
    except KeyboardInterrupt:
        click.echo("\nWorker stopped by user")
    except Exception as e:
        click.echo(f"Error starting worker: {e}", err=True)
        sys.exit(1)


@queue.command()
@click.argument("job_id")
@click.pass_context
def status(ctx: click.Context, job_id: str) -> None:
    """Check the status of a job."""
    project_root = ctx.obj["project_root"]
    if not project_root:
        click.echo("Error: Could not find project root", err=True)
        sys.exit(1)
    
    # Load configuration
    job_queue_config = load_job_queue_config(project_root)
    
    # Create manager
    manager = JobQueueManager(job_queue_config)
    
    # Get job
    job = manager.get_job(job_id)
    if not job:
        click.echo(f"Job not found: {job_id}")
        sys.exit(1)
    
    # Display job information
    click.echo(f"Job ID: {job.job_id}")
    click.echo(f"Pipeline: {job.pipeline_name}")
    click.echo(f"Status: {job.status.value}")
    click.echo(f"Queue: {job.queue_name}")
    click.echo(f"Created: {format_timestamp(job.created_at)}")
    
    if job.started_at:
        click.echo(f"Started: {format_timestamp(job.started_at)}")
    
    if job.ended_at:
        click.echo(f"Ended: {format_timestamp(job.ended_at)}")
        duration = job.duration()
        if duration:
            click.echo(f"Duration: {duration:.2f} seconds")
    
    if job.error:
        click.echo(f"Error: {job.error}")
    
    if job.retry_count > 0:
        click.echo(f"Retries: {job.retry_count}/{job.max_retries}")


@queue.command()
@click.argument("job_id")
@click.pass_context
def cancel(ctx: click.Context, job_id: str) -> None:
    """Cancel a job."""
    project_root = ctx.obj["project_root"]
    if not project_root:
        click.echo("Error: Could not find project root", err=True)
        sys.exit(1)
    
    # Load configuration
    job_queue_config = load_job_queue_config(project_root)
    
    # Create manager
    manager = JobQueueManager(job_queue_config)
    
    # Cancel job
    if manager.cancel_job(job_id):
        click.echo(f"Job cancelled: {job_id}")
    else:
        click.echo(f"Failed to cancel job: {job_id}")
        sys.exit(1)


@queue.command()
@click.option(
    "--queue",
    help="Filter by queue name",
)
@click.option(
    "--status",
    help="Filter by job status",
    type=click.Choice([s.value for s in JobStatus]),
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of jobs to show",
    default=20,
)
@click.pass_context
def list_jobs(
    ctx: click.Context,
    queue: Optional[str],
    status: Optional[str],
    limit: int,
) -> None:
    """List jobs."""
    project_root = ctx.obj["project_root"]
    if not project_root:
        click.echo("Error: Could not find project root", err=True)
        sys.exit(1)
    
    # Load configuration
    job_queue_config = load_job_queue_config(project_root)
    
    # Create manager
    manager = JobQueueManager(job_queue_config)
    
    # Get jobs
    jobs = manager.list_jobs(queue_name=queue, status=status, limit=limit)
    
    if not jobs:
        click.echo("No jobs found")
        return
    
    # Display jobs
    click.echo(f"{'ID':<8} {'Pipeline':<20} {'Status':<10} {'Queue':<10} {'Created'}")
    click.echo("-" * 80)
    
    for job in jobs:
        click.echo(
            f"{job.job_id[:8]:<8} "
            f"{job.pipeline_name[:20]:<20} "
            f"{job.status.value:<10} "
            f"{job.queue_name:<10} "
            f"{format_timestamp(job.created_at)}"
        )


@queue.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check the health of the job queue system."""
    project_root = ctx.obj["project_root"]
    if not project_root:
        click.echo("Error: Could not find project root", err=True)
        sys.exit(1)
    
    # Load configuration
    job_queue_config = load_job_queue_config(project_root)
    
    # Create manager
    manager = JobQueueManager(job_queue_config)
    
    # Get health status
    health_info = manager.health_check()
    
    click.echo(f"Status: {health_info['status']}")
    click.echo(f"Backend: {health_info['backend']}")
    
    if health_info["status"] == "healthy":
        if "workers" in health_info:
            click.echo(f"Workers: {health_info['workers']}")
        
        if "queues" in health_info:
            click.echo("\nQueue Statistics:")
            for queue_name, stats in health_info["queues"].items():
                click.echo(f"  {queue_name}:")
                click.echo(f"    Queued: {stats['queued']}")
                click.echo(f"    Running: {stats['started']}")
                click.echo(f"    Completed: {stats['finished']}")
                click.echo(f"    Failed: {stats['failed']}")
    else:
        click.echo(f"Error: {health_info.get('error', 'Unknown error')}")


def find_project_root() -> Optional[Path]:
    """Find the project root directory."""
    current_dir = Path.cwd()
    
    # Look for project.yml or pyproject.toml
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "project.yml").exists() or (parent / "pyproject.toml").exists():
            return parent
    
    return None


def load_job_queue_config(project_root: Path) -> Dict[str, Any]:
    """Load job queue configuration from project."""
    # Try to load from project.yml first
    project_file = project_root / "project.yml"
    if project_file.exists():
        try:
            import yaml
            with open(project_file, "r") as f:
                config = yaml.safe_load(f) or {}
                return config.get("job_queue", {})
        except ImportError:
            click.echo("Warning: PyYAML not installed, cannot load project.yml", err=True)
        except Exception as e:
            click.echo(f"Warning: Error loading project.yml: {e}", err=True)
    
    # Fallback to default configuration
    return {
        "backend": "rq",
        "job_defaults": {
            "timeout": 3600,
            "max_retries": 3,
            "retry_delay": 10.0,
            "result_ttl": 86400,
            "failure_ttl": 604800,
        },
        "backends": {
            "rq": {
                "redis_url": "redis://localhost:6379/0",
                "queues": ["default"],
            }
        }
    }


def format_timestamp(timestamp: float) -> str:
    """Format a timestamp for display."""
    from datetime import datetime
    
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")