"""Job model for flowerpower-job-queue."""

import enum
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import msgspec


class JobStatus(enum.Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SCHEDULED = "scheduled"


class Job(msgspec.Struct):
    """Job model representing a FlowerPower pipeline execution.
    
    This struct contains all information needed to execute a FlowerPower
    pipeline run asynchronously through a job queue backend.
    """
    
    # Core identification
    job_id: str
    pipeline_name: str
    base_dir: str
    
    # Execution parameters
    inputs: Dict[str, Any] = msgspec.field(default_factory=dict)
    final_vars: Optional[List[str]] = None
    config: Dict[str, Any] = msgspec.field(default_factory=dict)
    
    # Executor configuration
    executor: Optional[str] = None
    executor_cfg: Dict[str, Any] = msgspec.field(default_factory=dict)
    
    # Adapter configurations
    adapters: Dict[str, Dict[str, Any]] = msgspec.field(default_factory=dict)
    
    # Job metadata
    status: JobStatus = JobStatus.QUEUED
    queue_name: str = "default"
    priority: int = 0
    
    # Timing and execution control
    created_at: float = msgspec.field(default_factory=time.time)
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    timeout: Optional[int] = None
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: float = 10.0
    
    # Result and error handling
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    
    # Backend-specific fields
    backend_job_id: Optional[str] = None
    backend_data: Dict[str, Any] = msgspec.field(default_factory=dict)
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for serialization."""
        return msgspec.to_builtins(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create job from dictionary."""
        # Convert status back to enum if it's a string
        if isinstance(data.get("status"), str):
            data["status"] = JobStatus(data["status"])
        return msgspec.convert(data, cls)
    
    def duration(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        elif self.started_at:
            return time.time() - self.started_at
        return None
    
    def time_in_queue(self) -> float:
        """Calculate time spent in queue."""
        if self.started_at:
            return self.started_at - self.created_at
        return time.time() - self.created_at
    
    def is_finished(self) -> bool:
        """Check if job has finished execution."""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
    
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return (
            self.status == JobStatus.FAILED
            and self.retry_count < self.max_retries
        )
    
    def __str__(self) -> str:
        """String representation of the job."""
        return f"Job({self.job_id}, {self.pipeline_name}, {self.status.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"Job(job_id={self.job_id!r}, pipeline_name={self.pipeline_name!r}, "
            f"status={self.status.value!r}, queue_name={self.queue_name!r})"
        )


# Encoder/decoder for msgspec
encoder = msgspec.json.Encoder()
decoder = msgspec.json.Decoder(Job)


def encode_job(job: Job) -> bytes:
    """Encode a job to bytes."""
    return encoder.encode(job)


def decode_job(data: bytes) -> Job:
    """Decode a job from bytes."""
    return decoder.decode(data)