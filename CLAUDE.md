# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`flowerpower-job-queue` is a specialized job scheduling and queue management library designed exclusively for FlowerPower pipeline runs. It is NOT a general-purpose job queue system but purpose-built for asynchronous execution, scheduling, and distributed processing of FlowerPower data processing pipelines.

## Development Environment

- **Python**: 3.13+ required
- **Package Manager**: `uv` (not pip)
- **Build System**: uv_build
- **Virtual Environment**: `.venv/` (auto-created by uv)

## Common Commands

```bash
# Install dependencies
uv sync

# Install in development mode
uv pip install -e .

# Build the package
uv build

# Run tests (when implemented)
uv run pytest

# Run with specific Python version
uv run python <script>
```

## Architecture Overview

The project follows a plugin-based architecture with:

1. **Core Components** (`src/flowerpower_job_queue/core/`):
   - `base.py`: Abstract base classes for schedulers and queues
   - `config.py`: Unified configuration system
   - `exceptions.py`: Custom exception hierarchy

2. **Backend Registry** (`src/flowerpower_job_queue/backends/`):
   - Plugin system for supported backends: RQ, SAQ, ARQ, TaskIQ, Huey, Dramatiq
   - Each backend implements the core interfaces

3. **Job Management** (`src/flowerpower_job_queue/job/`):
   - `models.py`: Job data models with msgspec serialization
   - `lifecycle.py`: Job lifecycle management and state transitions

4. **Integration Points**:
   - Deep integration with Hamilton's execution graph
   - FlowerPower configuration system compatibility
   - Support for FlowerPower's adapter ecosystem

## Key Design Principles

- **Pipeline-Centric**: All jobs represent complete FlowerPower pipeline executions
- **Hamilton Integration**: Jobs carry full Hamilton execution context
- **Configuration Consistency**: Uses FlowerPower's existing configuration patterns
- **Backend Agnostic**: Common interface across all queue backends
- **Async-First**: Designed for asynchronous pipeline execution

## Implementation Status

- ✅ Project structure and dependencies configured
- ⏳ Core interfaces and base classes not yet implemented
- ⏳ Backend implementations pending
- ⏳ No tests or examples yet

## Important Notes

- This is a greenfield project with comprehensive documentation in `dev_docs/`
- The implementation plan details the complete architecture
- All jobs must preserve FlowerPower pipeline execution context
- Configuration should integrate seamlessly with existing FlowerPower configs