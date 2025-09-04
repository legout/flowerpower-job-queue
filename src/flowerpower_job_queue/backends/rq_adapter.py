"""RQ backend adapter for flowerpower-job-queue."""

import os
import sys
import time
from typing import Any, Dict, List, Optional

import redis
from rq import Queue, Worker, cancel_job, get_current_job
from rq.exceptions import NoSuchJobError
from rq.job import Job as RQJob

from ..core.base import BaseBackend
from ..core.job import Job, JobStatus, decode_job, encode_job


class RQBackend(BaseBackend):
    """RQ (Redis Queue) backend implementation.
    
    This backend uses RQ to provide a simple, reliable Redis-based job queue.
    """
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the RQ backend.
        
        Args:
            config: RQ backend configuration
                - redis_url: Redis connection URL
                - queues: List of queue names to create
                - default_timeout: Default job timeout in seconds
                - default_queue: Default queue name
                - worker_class: Worker class to use
                - async: Whether to run jobs asynchronously
        """
        super().__init__(config)
        
        # Connect to Redis
        self.redis_url = config.get("redis_url", "redis://localhost:6379/0")
        self.redis_conn = redis.from_url(self.redis_url)
        
        # Queue configuration
        self.queues = config.get("queues", ["default"])
        self.default_queue = config.get("default_queue", "default")
        self.default_timeout = config.get("default_timeout", 3600)
        self.is_async = config.get("async", True)
        
        # Worker configuration
        self.worker_class = config.get("worker_class", "rq.Worker")
        
        # Create queues
        self._queues: Dict[str, Queue] = {}
        for queue_name in self.queues:
            self._queues[queue_name] = Queue(
                name=queue_name,
                connection=self.redis_conn,
                default_timeout=self.default_timeout,
                is_async=self.is_async,
            )
    
    def get_queue(self, queue_name: Optional[str] = None) -> Queue:
        """Get a queue by name.
        
        Args:
            queue_name: Queue name, uses default if None
            
        Returns:
            The Queue instance
        """
        name = queue_name or self.default_queue
        if name not in self._queues:
            self._queues[name] = Queue(
                name=name,
                connection=self.redis_conn,
                default_timeout=self.default_timeout,
                is_async=self.is_async,
            )
        return self._queues[name]
    
    def enqueue(self, job: Job) -> Job:
        """Enqueue a job for execution.
        
        Args:
            job: The job to enqueue
            
        Returns:
            The updated job with backend identifiers
        """
        queue = self.get_queue(job.queue_name)
        
        # Prepare job execution context
        job_data = {
            "job": job.to_dict(),
            "base_dir": job.base_dir,
        }
        
        # Enqueue the job with RQ
        rq_job = queue.enqueue(
            _execute_flowerpower_job,
            job_data=job_data,
            job_id=job.job_id,
            timeout=job.timeout or self.default_timeout,
            result_ttl=job.result_ttl if hasattr(job, "result_ttl") else 86400,
            failure_ttl=job.failure_ttl if hasattr(job, "failure_ttl") else 604800,
            retry=job.max_retries,
            depends_on=None,
            job_timeout=job.timeout or self.default_timeout,
            description=f"FlowerPower pipeline: {job.pipeline_name}",
        )
        
        # Update job with backend information
        job.backend_job_id = rq_job.id
        job.backend_data = {
            "rq_job_id": rq_job.id,
            "queue_name": queue.name,
            "enqueued_at": rq_job.enqueued_at,
            "origin": rq_job.origin,
        }
        
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by its ID.
        
        Args:
            job_id: The job identifier
            
        Returns:
            The job if found, None otherwise
        """
        try:
            # Try to fetch from RQ
            rq_job = RQJob.fetch(job_id, connection=self.redis_conn)
            
            # Extract our job data from the job's kwargs
            if rq_job.kwargs and "job_data" in rq_job.kwargs:
                job_dict = rq_job.kwargs["job_data"]["job"]
                job = Job.from_dict(job_dict)
                
                # Update status and timing from RQ job
                job.status = self._map_rq_status(rq_job.get_status())
                job.backend_job_id = rq_job.id
                job.backend_data = {
                    "rq_job_id": rq_job.id,
                    "queue_name": rq_job.origin,
                    "enqueued_at": rq_job.enqueued_at,
                    "started_at": rq_job.started_at,
                    "ended_at": rq_job.ended_at,
                    "exc_info": rq_job.exc_info,
                }
                
                # Update result if available
                if rq_job.result:
                    job.result = rq_job.result
                
                # Update error information
                if rq_job.exc_info:
                    job.error = str(rq_job.exc_info)
                    job.traceback = rq_job.exc_info
                
                return job
            
            return None
            
        except NoSuchJobError:
            return None
    
    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get the status of a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            The job status if found, None otherwise
        """
        try:
            rq_job = RQJob.fetch(job_id, connection=self.redis_conn)
            return self._map_rq_status(rq_job.get_status())
        except NoSuchJobError:
            return None
    
    def _map_rq_status(self, rq_status: str) -> str:
        """Map RQ status to our JobStatus.
        
        Args:
            rq_status: RQ job status
            
        Returns:
            Mapped JobStatus value
        """
        status_mapping = {
            "queued": JobStatus.QUEUED,
            "started": JobStatus.RUNNING,
            "finished": JobStatus.COMPLETED,
            "failed": JobStatus.FAILED,
            "deferred": JobStatus.QUEUED,
            "scheduled": JobStatus.SCHEDULED,
            "stopped": JobStatus.CANCELLED,
        }
        return status_mapping.get(rq_status, JobStatus.QUEUED).value
    
    def start_worker(self, queues: List[str], **options: Any) -> None:
        """Start a worker process for the specified queues.
        
        Args:
            queues: List of queue names to listen on
            **options: Additional worker options
        """
        # Import worker class dynamically
        module_path, class_name = self.worker_class.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        worker_class = getattr(module, class_name)
        
        # Get queue instances
        queue_instances = [self.get_queue(q) for q in queues]
        
        # Create and start worker
        worker = worker_class(
            queue_instances,
            connection=self.redis_conn,
            name=options.get("name"),
            default_worker_ttl=options.get("worker_ttl", 420),
            default_result_ttl=options.get("result_ttl", 500),
            **{k: v for k, v in options.items() if k not in ["name", "worker_ttl", "result_ttl"]},
        )
        
        # Start working
        worker.work()
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        try:
            cancel_job(job_id, connection=self.redis_conn)
            return True
        except Exception:
            return False
    
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
        jobs = []
        
        # Get jobs from specified queue or all queues
        queues_to_check = (
            [self.get_queue(queue_name)] if queue_name else list(self._queues.values())
        )
        
        for queue in queues_to_check:
            # Get job IDs from queue
            job_ids = queue.get_job_ids()
            
            for job_id in job_ids[:limit]:  # Limit per queue
                job = self.get_job(job_id)
                if job and (status is None or job.status.value == status):
                    jobs.append(job)
                    
                    if len(jobs) >= limit:
                        return jobs
        
        return jobs
    
    def health_check(self) -> Dict[str, Any]:
        """Check the health of the RQ backend.
        
        Returns:
            Health status information
        """
        try:
            # Check Redis connection
            self.redis_conn.ping()
            
            # Get worker count
            workers = Worker.count(connection=self.redis_conn)
            
            # Get job counts per queue
            queue_stats = {}
            for name, queue in self._queues.items():
                queue_stats[name] = {
                    "queued": len(queue),
                    "started": len(queue.started_job_registry),
                    "finished": len(queue.finished_job_registry),
                    "failed": len(queue.failed_job_registry),
                    "deferred": len(queue.deferred_job_registry),
                    "scheduled": len(queue.scheduled_job_registry),
                }
            
            return {
                "status": "healthy",
                "backend": "RQ",
                "redis_url": self.redis_url,
                "workers": workers,
                "queues": queue_stats,
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "RQ",
                "error": str(e),
            }


def _execute_flowerpower_job(job_data: Dict[str, Any]) -> Any:
    """Execute a FlowerPower pipeline job.
    
    This function is called by RQ workers to run the actual pipeline.
    
    Args:
        job_data: Job execution data including the serialized job
        
    Returns:
        Pipeline execution result
    """
    # Get the current RQ job
    rq_job = get_current_job()
    if not rq_job:
        raise RuntimeError("Not running in RQ worker context")
    
    # Decode our job
    job_dict = job_data["job"]
    job = Job.from_dict(job_dict)
    base_dir = job_data["base_dir"]
    
    # Add base_dir to Python path
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    # Import FlowerPower
    try:
        from flowerpower import FlowerPower
    except ImportError:
        raise RuntimeError("FlowerPower not available in worker environment")
    
    # Update job status
    job.status = JobStatus.RUNNING
    job.started_at = time.time()
    
    # Create FlowerPower project and run pipeline
    try:
        project = FlowerPower(base_dir=base_dir)
        
        result = project.run(
            pipeline_name=job.pipeline_name,
            inputs=job.inputs,
            final_vars=job.final_vars,
            config=job.config,
            executor=job.executor,
            executor_cfg=job.executor_cfg,
            adapters=job.adapters,
            log_level=job.log_level,
        )
        
        # Update job with success
        job.status = JobStatus.COMPLETED
        job.ended_at = time.time()
        job.result = result
        
        return result
        
    except Exception as e:
        # Update job with error
        job.status = JobStatus.FAILED
        job.ended_at = time.time()
        job.error = str(e)
        
        # Retry logic
        if job.can_retry():
            job.retry_count += 1
            job.status = JobStatus.RETRYING
            # RQ will handle the retry based on the job's retry configuration
            
        raise