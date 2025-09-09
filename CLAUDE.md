# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-agent agentic framework built in Python. The project is in early development stage with minimal structure established.

## Development Setup

**Virtual Environment**: The project uses a Python virtual environment located in `.venv/`
- Activate: `source .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate` (Windows)
- Python version: >= 3.13 (as specified in pyproject.toml)

**Package Management**: Uses `uv` for fast Python package management with `pyproject.toml`
- Install project: `uv sync`
- Add dependencies: `uv add <package-name>`
- Add dev dependencies: `uv add --dev <package-name>`
- Run commands in venv: `uv run <command>`

## Project Structure

Currently minimal structure - expect to develop:
- Core framework modules for agent management
- Agent communication protocols
- Task orchestration systems  
- Multi-agent coordination mechanisms

## Development Commands

- **Install project**: `uv sync`
- **Run tests**: `uv run pytest` (once tests are added)
- **Format code**: `uv run black .` or `uv run ruff format .` (once formatters are configured)
- **Lint code**: `uv run ruff check .` or `uv run flake8 .` (once linters are configured)
- **Run Python**: `uv run python <script.py>`

## Architecture Considerations

For a multi-agent agentic framework, consider implementing:
- **Agent abstraction layer**: Base agent classes and interfaces
- **Communication protocols**: Message passing between agents
- **Task coordination**: Orchestration and workflow management
- **State management**: Shared state and synchronization
- **Plugin system**: Extensible agent capabilities
- **Configuration management**: Runtime agent configuration
- update the project use uv as package manager