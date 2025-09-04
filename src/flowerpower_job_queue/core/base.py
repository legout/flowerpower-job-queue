"""Abstract base classes for flowerpower-job-queue backends."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from .job import Job


class BaseBackend(ABC):
    """Abstract base class for job queue backends.
    
    All backend implementations must inherit from this class and
    implement all abstract methods.
    """
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the backend with configuration.
        
        Args:
            config: Backend-specific configuration dictionary
        """
        self.config = config
    
    @abstractmethod
    def enqueue(self, job: Job) -> Job:
        """Enqueue a job for execution.
        
        Args:
            job: The job to enqueue
            
        Returns:
            The updated job with backend-specific identifiers
        """
        ...
    
    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by its ID.
        
        Args:
            job_id: The job identifier
            
        Returns:
            The job if found, None otherwise
        """
        ...
    
    @abstractmethod
    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get the status of a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            The job status if found, None otherwise
        """
        ...
    
    @abstractmethod
    def start_worker(self, queues: List[str], **options: Any) -> None:
        """Start a worker process for the specified queues.
        
        Args:
            queues: List of queue names to listen on
            **options: Additional backend-specific worker options
        """
        ...
    
    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        ...
    
    @abstractmethod
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
        ...
    
    def health_check(self) -> Dict[str, Any]:
        """Check the health of the backend.
        
        Returns:
            Health status information
        """
        return {"status": "healthy", "backend": self.__class__.__name__}


class BaseScheduler(ABC):
    """Abstract base class for job schedulers.
    
    Schedulers handle delayed and recurring job execution.
    """
    
    def __init__(self, backend: BaseBackend) -> None:
        """Initialize the scheduler with a backend.
        
        Args:
            backend: The backend to use for job execution
        """
        self.backend = backend
    
    @abstractmethod
    def schedule(
        self,
        job: Job,
        run_at: Union[str, int],
        repeat: Optional[str] = None,
        **options: Any,
    ) -> str:
        """Schedule a job for future execution.
        
        Args:
            job: The job to schedule
            run_at: When to run the job (timestamp or cron expression)
            repeat: Optional repeat interval (cron expression)
            **options: Additional scheduler options
            
        Returns:
            The scheduled job ID
        """
        ...
    
    @abstractmethod
    def cancel_scheduled_job(self, job_id: str) -> bool:
        """Cancel a scheduled job.
        
        Args:
            job_id: The scheduled job ID
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        ...
    
    @abstractmethod
    def list_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """List all scheduled jobs.
        
        Returns:
            List of scheduled job information
        """
        ...