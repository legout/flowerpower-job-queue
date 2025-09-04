"""FlowerPower Job Queue - Specialized job scheduling for FlowerPower pipelines.

This library provides asynchronous execution, scheduling, and distributed processing
of FlowerPower pipelines through various queue backends.
"""

__version__ = "0.1.0"

from .core.manager import JobQueueManager
from .core.job import Job, JobStatus

# Register backends
from .backends.rq_adapter import RQBackend
JobQueueManager.register_backend("rq", RQBackend)

__all__ = [
    "JobQueueManager",
    "Job",
    "JobStatus",
    "RQBackend",
]