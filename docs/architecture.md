### Transformation to Architect (Winston)
*Transforming into Winston, the Architect.* As the architect, I’ll refine the design for the **flowerpower-job-queue** library based on your feedback regarding scheduling. The original design used APScheduler for cron/interval triggers, but after analyzing RQ's capabilities (built-in Repeat for intervals since v2.3.0 and CronScheduler since v2.4.0/2.5.0), we'll switch to RQ's native scheduling to reduce dependencies and improve integration. This aligns with the PRD's emphasis on minimal dependencies and extensibility—RQ's CronScheduler supports cron strings natively, making it a better fit than APScheduler for the initial RQ backend. For future backends (e.g., Taskiq), we can use their native schedulers or fallback to APScheduler if needed. The refined design maintains modularity, with the adapter handling backend-specific scheduling.

### Refined Architecture Design: FlowerPower-Job-Queue Library

#### 1. High-Level Overview
The library remains a standalone package (`flowerpower-job-queue`) importing FlowerPower without modifications. Key changes:
- **Scheduling**: Use RQ's built-in `CronScheduler` and `Repeat` for cron/interval jobs (require RQ >=2.5.0 for full cron support). This eliminates APScheduler as a dependency, reducing bloat while supporting `RunConfig.schedule` (cron strings) and intervals.
- **Pros of RQ Native Scheduling vs. APScheduler**:
  - Tighter integration with RQ (e.g., jobs enqueued directly to RQ queues).
  - No additional dependency (APScheduler adds ~100KB; RQ's scheduler is built-in).
  - Simpler setup: Run workers with `--with-scheduler` flag.
- **Cons**: Less flexible trigger types than APScheduler (e.g., no date-based without custom logic); backend-specific (future adapters may need APScheduler fallback).
- **Fallback**: For non-RQ backends, adapters can implement scheduling (e.g., Taskiq's scheduler or APScheduler).

**Diagram** (Updated Flow):
```
User/CLI/API → FlowerPowerProject (exposes enqueue/schedule/result) → JobQueueManager
JobQueueManager → QueueAdapter (e.g., RQAdapter) → Backend (RQ/Redis)
RQ Scheduler (CronScheduler/Repeat) → Trigger enqueue on cron/interval → RQ Queue
Workers (RQ Workers with --with-scheduler) → Dequeue → FlowerPowerProject.run() → Store result in job meta
Result Retrieval: JobQueueManager → RQAdapter → Job.result or meta['result']
```

#### 2. Key Components (Refined)
| Component | Description | Key Classes/Methods | Dependencies |
|-----------|-------------|---------------------|--------------|
| **JobQueueManager** | Orchestrator; handles enqueue, schedule, status, results, workers. Initializes adapters and backend scheduler. | - `__init__(project: FlowerPowerProject, backend: str = 'rq')`<br>- `enqueue(pipeline_name: str, run_config: RunConfig, priority: str = 'medium') → JobID`<br>- `schedule(..., schedule: str = '0 0 * * *', interval: int = None) → ScheduleID` (uses cron/interval)<br>- `result(pipeline_name: str | id: str) → dict`<br>- `get_queue_status(...) → dict`<br>- `start_workers(count: int)`<br>- `stop_workers()` | FlowerPower (`RunConfig`) |
| **QueueAdapter** (Abstract Base) | Interface for backends; now includes scheduling methods. | - `enqueue_task(task_data: dict) → JobID`<br>- `schedule_task(task_data: dict, schedule: str, interval: int) → ScheduleID`<br>- `get_result(job_id: str) → dict`<br>- `get_status(job_id: str) → str`<br>- `start_workers(count: int)`<br>- `stop_workers()` | ABC |
| **RQAdapter** (Initial Impl.) | Uses RQ for queuing; leverages `CronScheduler` for cron and `Repeat` for intervals. Serializes `RunConfig` to JSON/msgspec; stores results in `job.meta['result']`. | - Inherits `QueueAdapter`<br>- `enqueue_task(...): queue.enqueue(execute_pipeline, job_id=..., meta={'priority': priority})`<br>- `schedule_task(...): scheduler.cron(schedule, func=execute_pipeline, args=...)` or `Repeat(times=None, interval=interval)`<br>- Worker func: `def execute_pipeline(project_data, pipeline_name, run_config): project = FlowerPowerProject.load(**project_data); return project.run(pipeline_name, run_config)` | RQ >=2.5.0, Redis (via extras) |
| **Scheduler** | Backend-specific; for RQ, use `rq.scheduler.CronScheduler` and `Repeat` integrated in adapter. | - In `RQAdapter`: `self.scheduler = rq.scheduler.RQScheduler(connection=self.redis)`<br>- Trigger: `self.scheduler.cron(cron_string=schedule, func=enqueue_wrapper, args=...)` | RQ built-in (no APScheduler) |
| **CLI Subgroup** | Typer app for `queue` commands; dynamic loading. | - `queue_app = typer.Typer()`<br>- `@queue_app.command()` for `enqueue`, `schedule --schedule 'cron expr' --interval 60`, etc. | Typer (via extras) |
| **Integration Layer** | Attaches methods to `FlowerPowerProject` dynamically. | - Post-import: `FlowerPowerProject.enqueue = property(lambda self: self.job_queue.enqueue)` (use descriptor for methods) | FlowerPower |

#### 3. Data Flow (Refined)
1. **Enqueue**:
   - `project.enqueue(...)` → `JobQueueManager` serializes `run_config` (extend with `priority`).
   - `RQAdapter.enqueue_task(...)` → `queue.enqueue(execute_pipeline, meta={'result': None, 'priority': priority})` → Job ID.
2. **Scheduling**:
   - `project.schedule(..., schedule='0 0 * * *', interval=60)` → `RQAdapter.schedule_task(...)`.
   - If cron: `scheduler.cron(schedule, func=execute_pipeline, args=serialized_data)`.
   - If interval: Use `Repeat(times=None, interval=interval)` with `enqueue_in(timedelta(seconds=interval))`.
   - Wrapper enqueues with stored `run_config` (handles `max_retries`, etc.).
3. **Worker Execution**:
   - Run RQ workers: `rq worker --with-scheduler` (enables built-in scheduler).
   - Dequeue: Deserialize, load `FlowerPowerProject`, call `run()`; update `job.meta['result'] = output`.
4. **Status/Result Retrieval**:
   - `get_queue_status(id)`: `job.get_status()` (leverages RQ's states).
   - `result(id)`: `job.result` or `job.meta['result']`.
5. **CLI Loading**:
   - `pyproject.toml` entrypoints: `[project.entry-points."flowerpower.cli_extensions"] queue = "flowerpower_job_queue.cli:queue_app"`.
   - FlowerPower loads: `for ep in entry_points(group='flowerpower.cli_extensions'): app.add_typer(ep.load())`.

#### 4. Packaging and Build (Unchanged)
- **pyproject.toml** (with `uv`): Define deps, extras (e.g., `optional-dependencies.rq = ['rq>=2.5.0', 'redis>=5.0']`), entrypoints.
- **uv Workflow**: `uv sync`, `uv lock`, `uv build`, `uv publish`.

#### 5. Non-Functional Design (Refined)
- **Performance**: RQ scheduler polls efficiently (every 1s for active jobs); `CronScheduler` scales with Redis.
- **Reliability**: RQ's built-in retry (via `run_config`); scheduler persistence in Redis.
- **Extensibility**: Adapters override scheduling (e.g., TaskiqAdapter uses Taskiq scheduler).
- **Testing**: Mock RQ/Redis; test cron triggers with time mocks.

#### 6. Risks and Mitigations (Updated)
- **Risk**: RQ scheduler limitations (e.g., no advanced triggers). **Mitigation**: Adapter fallback to APScheduler for complex needs; docs highlight RQ's cron/interval focus.
- **Risk**: Version dependency (RQ >=2.5.0). **Mitigation**: Pin in `pyproject.toml`; test with multiple RQ versions.

#### 7. Implementation Guidelines (Refined)
- **Directory Structure**: Unchanged.
- **RQ Scheduling Code Example**:
  ```python
  from rq import Queue
  from rq.scheduler import RQScheduler

  class RQAdapter(QueueAdapter):
      def __init__(self, connection):
          self.queue = Queue(connection=connection)
          self.scheduler = RQScheduler(connection=connection)

      def schedule_task(self, task_data, schedule, interval=None):
          if schedule:  # Cron
              self.scheduler.cron(schedule, func=self.execute_pipeline, args=task_data)
          elif interval:  # Interval
              self.queue.enqueue_in(timedelta(seconds=interval), self.execute_pipeline, args=task_data, repeat=Repeat(times=None, interval=interval))
  ```
- **Start with RQ**: Implement `RQAdapter` with built-in scheduler; stub APScheduler fallback for other backends.
