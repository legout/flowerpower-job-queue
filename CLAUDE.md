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

# Code formatting and quality
uv run black src/
uv run isort src/
uv run mypy src/
uv run ruff check src/
```

## Architecture Overview

The project follows a plugin-based architecture detailed in `docs/spec.md`:

1. **Core Components** (to be implemented in `src/flowerpower_job_queue/core/`):
   - `base.py`: Abstract base classes for schedulers and queues
   - `job.py`: Job model definition with msgspec serialization
   - `manager.py`: JobQueueManager implementation

2. **Backend Registry** (to be implemented in `src/flowerpower_job_queue/backends/`):
   - Plugin system for supported backends: RQ, SAQ, ARQ, TaskIQ, Huey, Dramatiq
   - Each backend implements the core interfaces
   - Initial focus on RQ and TaskIQ backends

3. **CLI Integration** (to be implemented in `src/flowerpower_job_queue/cli/`):
   - `main.py`: CLI commands extending FlowerPower's CLI
   - `flowerpower queue` subcommand group

4. **Integration Points**:
   - Deep integration with Hamilton's execution graph
   - FlowerPower configuration system via `flowerpower.cfg`
   - Support for FlowerPower's adapter ecosystem

## Key Design Principles

- **Pipeline-Centric**: All jobs represent complete FlowerPower pipeline executions
- **Hamilton Integration**: Jobs carry full Hamilton execution context
- **Configuration Consistency**: Uses FlowerPower's existing configuration patterns
- **Backend Agnostic**: Common interface across all queue backends
- **Async-First**: Designed for asynchronous pipeline execution

## Implementation Status

- ✅ Project structure, dependencies, and tooling configured
- ✅ Comprehensive specification in `docs/spec.md`
- ❌ Core interfaces and base classes not yet implemented
- ❌ Backend implementations pending
- ❌ No tests or examples yet

## Configuration

The job queue system integrates with FlowerPower's configuration system:

```toml
[job_queue]
backend = "rq"  # or "taskiq"
enabled = true

# Backend-specific settings
[job_queue.rq]
redis_url = "redis://localhost:6379/0"
default_queue = "default"

[job_queue.taskiq]
broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"
```

## Development Workflow

When working on this project, follow this workflow:

1. **Architecture Planning**: Use the architect subagent to analyze the problem, read the specification in `docs/spec.md`, and review the todo list in `tasks/todo.md` (if it exists)

2. **Task Management**: Create or update `tasks/todo.md` using the taskmaster subagent. Check off todo items as they are completed

3. **Plan Verification**: Before beginning implementation work, review the plan with the project lead for approval

4. **Implementation**: Begin working on todo items, marking them as complete as you go using the coder subagent

5. **Code Review**: After each coding task, use the reviewer subagent to analyze the latest code changes. Apply recommended changes using either the code simplifier or coder subagent, whichever is more appropriate

6. **Simplicity First**: Make every task and code change as simple as possible. Avoid massive or complex changes. Each change should impact as little code as possible

7. **Review Documentation**: After completing work, add a review section to `tasks/todo.md` summarizing the changes made and any other relevant information

## Important Notes

- This is a greenfield project with zero implementation but comprehensive planning
- The detailed implementation plan is in `docs/spec.md`
- All jobs must preserve FlowerPower pipeline execution context
- Configuration should integrate seamlessly with existing FlowerPower configs
- Uses modern toolchain: uv, Python 3.13, uv_build

## Library Documentation Research

When implementing backend integrations (RQ, TaskIQ, etc.) and you're unsure about syntax, APIs, or best practices:

1. **Use context7 MCP server** for up-to-date library documentation:
   - Use `mcp__context7__resolve-library-id` to find the correct library ID
   - Use `mcp__context7__get-library-docs` to retrieve specific documentation

2. **Use deepwiki MCP server** for GitHub repository documentation:
   - Use `mcp__deepwiki__ask_question` to get answers about implementation details
   - Use `mcp__deepwiki__read_wiki_contents` for comprehensive guides

Always research the current best practices and APIs before implementing backend integrations.

## FlowerPower Context Research

When unsure about FlowerPower syntax, patterns, or best practices:

1. **Search the context documentation**:
   - Use `Grep` to search for relevant sections in `docs/context/flowerpower.md` before reading the entire file
   - Search for specific keywords like "PipelineManager", "RunConfig", "configuration", etc.
   - Look for API documentation and examples related to your implementation needs

2. **Common search patterns**:
   ```bash
   # Search for specific API documentation
   grep -n "PipelineManager" docs/context/flowerpower.md
   grep -n "RunConfig" docs/context/flowerpower.md
   grep -n "configuration" docs/context/flowerpower.md
   
   # Search for integration patterns
   grep -n -A5 -B5 "adapter" docs/context/flowerpower.md
   grep -n -A10 "CLI" docs/context/flowerpower.md
   ```

3. **Integration guidelines**:
   - Study how FlowerPower handles configuration loading and management
   - Understand the PipelineManager interface and execution patterns
   - Review how adapters are integrated and configured
   - Examine the CLI structure for extending it properly