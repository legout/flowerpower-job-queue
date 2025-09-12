# Product Requirements Document: FlowerPower-Job-Queue Library

## 1. Document Overview
- **Version**: 1.1  
- **Date**: September 12, 2025  
- **Author**: John (Product Manager)  
- **Description**: This PRD defines requirements for **flowerpower-job-queue**, a modular Python library enabling async enqueueing, scheduling, and result retrieval for FlowerPower pipelines. It depends on FlowerPower without modifying it, using a multi-backend adapter pattern (starting with RQ) and integrates with FlowerPower’s CLI (`flowerpower queue`) and API (`FlowerPowerProject`).  
- **Scope**: Greenfield library development; CLI subcommands under `flowerpower queue`; API methods via `FlowerPowerProject`. Out of scope: FlowerPower modifications, advanced UI.  
- **Assumptions**: FlowerPower vX.X installed; users have Redis for RQ (optional for other backends).  
- **Dependencies**: FlowerPower (core), RQ (initial backend), APScheduler (scheduling), Typer (CLI).  

## 2. User Personas and Needs
- **Primary Persona: Data Engineer (Bob)**: Manages distributed pipelines; needs non-blocking execution, scheduling, and monitoring (e.g., `flowerpower queue status id=1234`).  
- **Secondary Persona: Developer (Alice)**: Builds pipelines; wants simple API (e.g., `project.enqueue(...)`) and CLI (e.g., `flowerpower queue enqueue pipeline123`).  
- **Key Needs**:  
  - Seamless integration with FlowerPower’s CLI and API.  
  - Extensible backends for scalability.  
  - Easy result retrieval by pipeline name or job ID.  

## 3. User Stories
Prioritized using MoSCoW method (Must-have, Should-have, Could-have, Won't-have).

| Priority | User Story | Acceptance Criteria |
|----------|------------|----------------------|
| Must | As a developer, I can enqueue a pipeline via API so that it runs asynchronously. | - `project.enqueue(pipeline_name, run_config, priority='medium', backend='rq')` returns job ID.<br>- Integrates with extended `RunConfig` (add `priority`, `schedule`, `backend`).<br>- Non-blocking; uses RQ to queue task calling `project.run()`. |
| Must | As a data engineer, I can retrieve job status/results via CLI or API by pipeline name or ID. | - CLI: `flowerpower queue status [pipeline_name \| id=1234]` shows pending/running/failed.<br>- CLI: `flowerpower queue result [pipeline_name \| id=1234]` returns output (e.g., dict from `run()`).<br>- API: `project.get_queue_status(id=1234)` and `project.result(id=1234)`. |
| Must | As a user, I can manage workers via CLI for distributed execution. | - `flowerpower queue worker start --count 4 --backend rq` spawns RQ workers executing via FlowerPower.<br>- `flowerpower queue worker stop --backend rq` gracefully stops workers.<br>- Supports multi-machine via Redis. |
| Should | As a developer, I can schedule pipelines via API/CLI. | - `project.schedule(pipeline_name, run_config, schedule='0 0 * * *')` uses APScheduler with RQ.<br>- CLI: `flowerpower queue schedule <pipeline_name> --schedule '0 0 * * *'`. |
| Should | As a data engineer, I can extend the library with new backends. | - Implement `QueueAdapter` subclass (e.g., `TaskiqAdapter`).<br>- Register via config; fallback to RQ if unspecified. |
| Could | As a user, I can view queue metrics (e.g., length) via CLI. | - `flowerpower queue metrics --backend rq` shows pending/completed counts. |
| Won't | Advanced dashboard UI; non-RQ backends in v1.0. | N/A |

## 4. Functional Requirements
- **API Layer**:
  - `JobQueueManager` class: Core manager with `enqueue(project, pipeline_name, run_config, priority='medium', backend='rq')`, `schedule(...)`, `result(pipeline_name | id)`, `get_queue_status(pipeline_name | id)`, `start_workers(count, backend)`, `stop_workers(backend)`.
  - Integration: Mixin or dynamic attribute to `FlowerPowerProject` (e.g., `project.job_queue = JobQueueManager(project)`; expose `enqueue()`, etc., directly).
  - Backend Selection: `backend` param defaults to 'rq'; validate via adapter registry.
- **CLI Layer**:
  - Subgroup: `queue` under `flowerpower` (e.g., `flowerpower queue enqueue`).
  - Commands: `enqueue <pipeline_name> --priority high --backend rq`, `status [pipeline_name | id=1234]`, `result [pipeline_name | id=1234]`, `schedule <pipeline_name> --schedule 'cron expr'`, `worker start --count N --backend rq`, `worker stop`.
  - Implementation: Use Typer’s `app.add_typer(queue_app)`; register via `pyproject.toml`’s `[project.entry-points."flowerpower.cli_extensions"]` for dynamic CLI loading.
- **Adapter Pattern**:
  - Base: `QueueAdapter` with abstract methods (`enqueue_task()`, `get_result(id)`, `get_status(id)`, `start_workers()`, `stop_workers()`).
  - Initial: `RQAdapter` using RQ/Redis; store job metadata (pipeline_name, serialized `RunConfig`).
  - Extensibility: Users subclass and register (e.g., `register_adapter('taskiq', TaskiqAdapter)`).
- **Scheduling**:
  - Integrate APScheduler: Trigger `enqueue()` on cron expressions from `RunConfig.schedule`.
- **Result Storage**:
  - Store `run()` output in backend (e.g., RQ job metadata in Redis); retrieve via pipeline_name or ID.
  - Serialize `RunConfig` using msgspec (FlowerPower’s serializer) or JSON.
- **Packaging**:
  - Use `pyproject.toml` managed by `uv` for dependencies, extras, and entrypoints.
  - Define: `dependencies = ['flowerpower']`, `optional-dependencies.rq = ['rq>=1.0', 'apscheduler>=3.0']`, `optional-dependencies.cli = ['typer>=0.9']`.
  - CLI Entrypoint: Register `queue` subcommands via `[project.entry-points."flowerpower.cli_extensions"]`.
  - Build: Use `uv build`, `uv publish`; include `uv.lock` for reproducibility.

## 5. Non-Functional Requirements
- **Performance**: Enqueue < 100ms; support 1000+ concurrent jobs (RQ/Redis scaling).
- **Security**: Safe serialization (msgspec/JSON); validate CLI/API inputs.
- **Reliability**: Retries via `RunConfig.max_retries`; `on_failure` for queue errors.
- **Usability**: CLI `--help` and shell completion via Typer.
- **Maintainability**: 80%+ test coverage; docs with API/CLI examples (e.g., `project.enqueue()`, `flowerpower queue status`).
- **Compatibility**: Python 3.8+; FlowerPower >= current version.
- **Packaging**: `pyproject.toml` with `uv`; no `setup.py`. Include `uv.lock`.

## 6. Success Metrics and KPIs
- **Adoption**: 50% of FlowerPower users install/enable in beta (PyPI downloads).
- **Usability**: NPS > 8/10 from beta testers (e.g., CLI/API ease).
- **Performance**: <5% failure rate on queued jobs; benchmark vs. `run()`.
- **Extensibility**: One community backend (e.g., Taskiq) contributed in 6 months.
- **Validation**: Integration tests pass; e2e scenarios (enqueue → exec → result).

## 7. Risks and Mitigations
- **Risk**: CLI integration fails if FlowerPower updates break entrypoints. **Mitigation**: Use custom `flowerpower.cli_extensions` group; test with multiple FlowerPower versions.
- **Risk**: Serialization issues with complex `RunConfig`. **Mitigation**: Use msgspec; fallback to JSON.
- **Risk**: Redis dependency overhead. **Mitigation**: Optional extras; docs for local dev without Redis.
- **Risk**: `uv` adoption barrier. **Mitigation**: Provide `requirements.txt` export; clear `uv` setup guide.

## 8. Appendix
- **Wireframes/Sketches**: N/A (API/CLI focus).
- **References**: FlowerPower repomix-output.md; RQ docs; Typer subcommands guide; `uv` packaging guide.