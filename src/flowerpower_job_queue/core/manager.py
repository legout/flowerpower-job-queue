"""JobQueueManager for managing queue backends and configuration."""

import os
import uuid
from typing import Any, Dict, List, Optional, Type

from .base import BaseBackend
from .job import Job, JobStatus


class JobQueueManager:
    """Manager for job queue backends and configuration.
    
    This class provides a unified interface for managing different queue backends
    and handles configuration loading from FlowerPower's config system.
    """
    
    # Registry of available backends
    _backends: Dict[str, Type[BaseBackend]] = {}
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the manager with configuration.
        
        Args:
            config: Job queue configuration from FlowerPower
        """
        self.config = config
        self._backend_instance: Optional[BaseBackend] = None
        
    @classmethod
    def register_backend(cls, name: str, backend_class: Type[BaseBackend]) -> None:
        """Register a backend implementation.
        
        Args:
            name: Backend name (e.g., 'rq', 'taskiq')
            backend_class: Backend implementation class
        """
        cls._backends[name] = backend_class
    
    @classmethod
    def get_available_backends(cls) -> List[str]:
        """Get list of available backend names."""
        return list(cls._backends.keys())
    
    @property
    def backend(self) -> BaseBackend:
        """Get the configured backend instance."""
        if self._backend_instance is None:
            self._backend_instance = self._create_backend()
        return self._backend_instance
    
    def _create_backend(self) -> BaseBackend:
        """Create the backend instance based on configuration."""
        backend_name = self.config.get("backend", "rq")
        
        if backend_name not in self._backends:
            available = ", ".join(self._backends.keys())
            raise ValueError(
                f"Unknown backend '{backend_name}'. Available backends: {available}"
            )
        
        backend_class = self._backends[backend_name]
        backend_config = self.config.get("backends", {}).get(backend_name, {})
        
        return backend_class(backend_config)
    
    def create_job(
        self,
        pipeline_name: str,
        base_dir: str,
        inputs: Optional[Dict[str, Any]] = None,
        final_vars: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        executor: Optional[str] = None,
        executor_cfg: Optional[Dict[str, Any]] = None,
        adapters: Optional[Dict[str, Dict[str, Any]]] = None,
        queue_name: Optional[str] = None,
        priority: int = 0,
        timeout: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 10.0,
        log_level: str = "INFO",
        **kwargs: Any,
    ) -> Job:
        """Create a new job with the given parameters.
        
        Args:
            pipeline_name: Name of the pipeline to execute
            base_dir: Base directory for the project
            inputs: Input variables for the pipeline
            final_vars: List of final variables to compute
            config: Additional configuration
            executor: Hamilton executor to use
            executor_cfg: Executor configuration
            adapters: Adapter configurations
            queue_name: Queue to enqueue the job in
            priority: Job priority (higher = more priority)
            timeout: Job timeout in seconds
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            log_level: Logging level
            **kwargs: Additional job parameters
            
        Returns:
            The created job
        """
        # Apply defaults from configuration
        job_defaults = self.config.get("job_defaults", {})
        
        job = Job(
            job_id=str(uuid.uuid4()),
            pipeline_name=pipeline_name,
            base_dir=base_dir,
            inputs=inputs or {},
            final_vars=final_vars,
            config=config or {},
            executor=executor,
            executor_cfg=executor_cfg or {},
            adapters=adapters or {},
            queue_name=queue_name or job_defaults.get("queue_name", "default"),
            priority=priority,
            timeout=timeout or job_defaults.get("timeout"),
            max_retries=max_retries if max_retries is not None else job_defaults.get("max_retries", 3),
            retry_delay=retry_delay if retry_delay is not None else job_defaults.get("retry_delay", 10.0),
            log_level=log_level or job_defaults.get("log_level", "INFO"),
            result_ttl=job_defaults.get("result_ttl", 86400),
            failure_ttl=job_defaults.get("failure_ttl", 604800),
            **kwargs,
        )
        
        return job
    
    def enqueue(self, job: Job) -> Job:
        """Enqueue a job for execution.
        
        Args:
            job: The job to enqueue
            
        Returns:
            The updated job with backend identifiers
        """
        return self.backend.enqueue(job)
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by its ID.
        
        Args:
            job_id: The job identifier
            
        Returns:
            The job if found, None otherwise
        """
        return self.backend.get_job(job_id)
    
    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get the status of a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            The job status if found, None otherwise
        """
        return self.backend.get_job_status(job_id)
    
    def start_worker(self, queues: Optional[List[str]] = None, **options: Any) -> None:
        """Start a worker process.
        
        Args:
            queues: List of queue names to listen on
            **options: Additional backend-specific worker options
        """
        if queues is None:
            queues = self.config.get("backends", {}).get(
                self.config.get("backend", "rq"), {}
            ).get("queues", ["default"])
        
        self.backend.start_worker(queues, **options)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        return self.backend.cancel_job(job_id)
    
    def list_jobs(
        self,
        queue_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Job]:
        """List jobs with optional filtering.
        
        Args:
            queue_name: Filter by queue name
            status: Filter by job status
            limit: Maximum number of jobs to return
            
        Returns:
            List of matching jobs
        """
        return self.backend.list_jobs(queue_name, status, limit)
    
    def health_check(self) -> Dict[str, Any]:
        """Check the health of the job queue system.
        
        Returns:
            Health status information
        """
        return self.backend.health_check()