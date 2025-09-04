# FlowerPower JobQueue - Software Design Document

## 1. Overview

This document outlines the software design for `flowerpower-job-queue`, a specialized job scheduling and queue management library designed exclusively as a plugin for the FlowerPower framework. Its core purpose is to enable the asynchronous execution, scheduling, and distributed processing of FlowerPower pipelines.

This library is **not** a general-purpose job queue system. It is tightly integrated with FlowerPower's architecture, including its configuration, execution model, and command-line interface.

This initial specification details the implementation of two primary backends:
1.  **RQ (Redis Queue):** A simple and robust Redis-based queue for straightforward background processing.
2.  **TaskIQ:** A modern, flexible asynchronous task queue offering support for multiple brokers and advanced features.

## 2. Project Goals

-   **Seamless Integration**: Act as a natural extension of the FlowerPower framework.
-   **Unified Interface**: Provide a single, consistent API (`run_async`) and CLI for enqueuing pipeline runs, regardless of the backend used.
-   **Backend Flexibility**: Support multiple queue backends through a plugin-based adapter system.
-   **Configuration-Driven**: Leverage FlowerPower's existing configuration system (`flowerpower.cfg`) for all settings, while allowing for programmatic and CLI-based overrides.
-   **Robust Execution**: Ensure reliable pipeline execution with support for timeouts, retries, and error handling.
-   **Observability**: Provide mechanisms for monitoring job status and worker health.

## 3. Architecture

### 3.1. Core Components

-   **JobQueueManager**: The main entry point, responsible for loading backend-specific configurations and providing the user-facing API.
-   **BaseBackend (Abstract Class)**: Defines the common interface that all backend adapters (e.g., RQ, TaskIQ) must implement. This includes methods like `enqueue`, `get_job`, and `start_worker`.
-   **Backend Adapters**: Concrete implementations of `BaseBackend` for each supported queueing system (e.g., `RQBackend`, `TaskIQBackend`).
-   **Job Model**: A structured data class (`Job`) that encapsulates all information required to execute a FlowerPower pipeline run. This object is serialized and passed to the message queue.
-   **CLI Extension**: A new command group (`flowerpower queue`) integrated into the main FlowerPower CLI.

### 3.2. Plugin Integration with FlowerPower

The library will integrate with FlowerPower in two primary ways:

1.  **Programmatic API**: A new method, `run_async()`, will be added to the `FlowerPowerProject` class. This method will have a similar signature to the existing `run()` method but will delegate the execution to the configured job queue backend.

    ```python
    # Example of future usage
    from flowerpower import FlowerPower

    project = FlowerPower()
    job = project.run_async(
        "my_pipeline",
        inputs={"data_date": "2025-09-05"}
    )
    print(f"Successfully enqueued job: {job.id}")
    ```

2.  **Command-Line Interface**: A new subcommand, `queue`, will be added to the `flowerpower` CLI.

    ```bash
    # Example of future CLI usage
    flowerpower queue enqueue my_pipeline --inputs '{"data_date": "2025-09-05"}'
    flowerpower queue worker --queue high_priority
    ```

### 3.3. Directory Structure

```
src/flowerpower_job_queue/
├── __init__.py
├── py.typed
├── core/
│   ├── __init__.py
│   ├── base.py          # Abstract base classes for backends
│   ├── job.py           # Job model definition
│   └── manager.py       # JobQueueManager
├── backends/
│   ├── __init__.py
│   ├── rq_adapter.py
│   └── taskiq_adapter.py
└── cli/
    ├── __init__.py
    └── main.py          # Click command definitions for the 'queue' subcommand
```

## 4. Configuration

### 4.1. Integration with `flowerpower.cfg`

As requested, the job queue configuration will be integrated directly into FlowerPower's existing configuration system. A new `job_queue` section will be added to the project's main configuration file (e.g., `project.yml`). This approach centralizes all settings and leverages FlowerPower's existing config loading and validation mechanisms.

### 4.2. Configuration Schema

The `job_queue` section will contain settings for the active backend, backend-specific parameters, and default job options.

**Example `project.yml`:**

```yaml
name: my_flowerpower_project

# ... other project settings

job_queue:
  # Select the active backend: "rq" or "taskiq"
  backend: "rq"

  # Default settings for all jobs, can be overridden at enqueue time
  job_defaults:
    timeout: 3600         # seconds
    max_retries: 3
    retry_delay: 10.0     # seconds
    result_ttl: 86400     # 1 day
    failure_ttl: 604800   # 7 days

  # Configuration for each backend. Only the active backend's config is used.
  backends:
    rq:
      redis_url: "redis://localhost:6379/0"
      queues:
        - "default"
        - "high_priority"
      # Unique UI/Worker settings for RQ
      worker_class: "rq.Worker"

    taskiq:
      # TaskIQ can use various brokers
      broker: "redis" # or "nats", "kafka", "postgres"
      result_backend: "redis"
      redis_url: "redis://localhost:6379/1"
      queues:
        - "default"
        - "async_tasks"
      # Unique UI/Worker settings for TaskIQ
      worker_concurrency: 10
```

### 4.3. Configuration Loading

The `JobQueueManager` will receive the `job_queue` configuration section from the main `FlowerPowerProject` instance. This ensures that configuration is loaded once, using FlowerPower's standard mechanisms. CLI arguments will take the highest precedence, allowing users to override specific settings for a single command.

## 5. Backends

### 5.1. Backend Abstraction (`BaseBackend`)

All backend adapters will implement a common interface:

```python
class BaseBackend(ABC):
    def __init__(self, config: dict):
        ...

    @abstractmethod
    def enqueue(self, job: Job) -> Job:
        """Serializes and enqueues a job, returning the updated job model."""
        ...

    @abstractmethod
    def start_worker(self, queues: list[str], **options):
        """Starts a worker process for the specified queues."""
        ...
```

### 5.2. Supported Backends

-   **RQ (Redis Queue):**
    -   **Role:** Provides a simple, reliable, synchronous (in terms of function execution) job queue based on Redis. It's ideal for projects needing a straightforward and battle-tested solution.
    -   **Configuration:** Primarily requires a `redis_url` and a list of `queues`.
    -   **UI/Worker:** The worker is a standard RQ worker. The CLI will provide a wrapper to launch `rq worker`.

-   **TaskIQ:**
    -   **Role:** A modern, async-native task manager with high flexibility. It supports dependency injection, multiple brokers (Redis, NATS, Kafka, etc.), and configurable result backends.
    -   **Configuration:** Requires `broker`, `result_backend`, and connection details (e.g., `redis_url`).
    -   **UI/Worker:** The worker is a TaskIQ worker. The CLI will provide a wrapper to launch the TaskIQ worker process, potentially with options like `--reload` for development.

## 6. Job Model

The `Job` model is the core data structure for an asynchronous pipeline run. It is designed to be self-contained, holding all information a worker needs to execute a `flowerpower pipeline run` command. The structure defined in `docs/implementation_plan.md` will be used, as it perfectly captures the execution context of a FlowerPower pipeline.

**Key Fields:**
-   `job_id`: Unique identifier.
-   `pipeline_name`: The pipeline to run.
-   `base_dir`: The project's base directory.
-   `inputs`, `final_vars`, `config`: The standard `run` parameters.
-   `executor`, `executor_cfg`: Hamilton executor settings.
-   `adapter` configurations: Full support for FlowerPower's adapter ecosystem.
-   Execution controls: `timeout`, `max_retries`, `log_level`, etc.
-   Queue metadata: `queue_name`, `priority`.

## 7. User Interface

### 7.1. Programmatic API

The primary API will be `FlowerPowerProject.run_async()`. It will construct a `Job` object from its arguments and the project's configuration, then pass it to the configured backend's `enqueue` method.

### 7.2. Command-Line Interface (CLI)

A new `queue` subcommand will be added to the `flowerpower` CLI.

-   `flowerpower queue enqueue <pipeline_name> [options...]`:
    -   Creates and enqueues a job.
    -   Accepts the same arguments as `flowerpower pipeline run` (e.g., `--inputs`, `--final-vars`, `--log-level`).
    -   Additional options: `--queue`, `--priority`.

-   `flowerpower queue worker [options...]`:
    -   Starts a worker process.
    -   Arguments are passed to the underlying backend's worker command.
    -   Example: `flowerpower queue worker --queue default --queue high_priority`.
    -   Each backend can expose unique options via this command, for example `flowerpower queue worker --concurrency 10` for TaskIQ.

-   `flowerpower queue status <job_id>`:
    -   Checks the status of a specific job.

## 8. Implementation Phases

1.  **Phase 1: Core Architecture & RQ Backend**
    -   Implement the `BaseBackend` ABC and `Job` model.
    -   Develop the `JobQueueManager`.
    -   Integrate configuration with `flowerpower.cfg` by defining the `job_queue` schema.
    -   Implement the `RQBackend` adapter.
    -   Create the initial `flowerpower queue` CLI with `enqueue` and `worker` commands for RQ.
    -   Add the `run_async` method to `FlowerPowerProject`.

2.  **Phase 2: TaskIQ Backend**
    -   Implement the `TaskIQBackend` adapter.
    -   Extend the `job_queue` configuration schema with TaskIQ-specific options.
    -   Enhance the `flowerpower queue worker` command to support TaskIQ's specific worker options.

3.  **Phase 3: Testing and Documentation**
    -   Develop a comprehensive test suite with unit tests for each backend and integration tests with a sample FlowerPower project.
    -   Write user documentation covering configuration, API usage, and CLI commands for both backends.
    -   Create examples demonstrating how to use the job queue for common use cases.