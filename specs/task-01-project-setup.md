# Task 01: Project Setup and Environment Configuration

## Objective
Set up the Python project structure, dependencies, Docker-based Oracle Database 23ai, and environment configuration.

## Requirements Covered
- REQ-1: Startup and Invocation (environment file, Docker container, database connection)

## Acceptance Criteria

### Project Structure
- Create a Python package with a clear module structure (e.g., `codesherpa/`)
- Set up `pyproject.toml` or `setup.py` with all dependencies
- Dependencies: `langchain`, `langgraph`, `oracledb`, `voyageai`
- Create an `.env.example` file documenting required environment variables

### Oracle Database 23ai (Docker)
- Provide a `docker-compose.yml` to run `container-registry.oracle.com/database/free:latest` with port 1521 exposed
- Create a database initialization script that sets up the required schema
- Create a connection utility that reads credentials from `.env`

### API Client Setup
- Create a Voyage AI client wrapper that reads the API key from `.env`
- Create an LLM client wrapper (via LangChain) that reads config from `.env`
- Validate that all required environment variables are present on startup

### CLI Entry Point
- Create a basic CLI entry point using `argparse` or `click`
- Accept `--project` name and a source path or GitHub URL as arguments
- Display a clear error if the Docker container is not running and no cloud connection is configured

## Tests
- Verify Oracle Database container is running and connectable
- Verify Voyage AI embedding API returns a valid 1024-dimensional vector
- Verify LLM API returns a valid response
- Verify `.env` is read correctly and no credentials are hardcoded
- Verify CLI displays usage information and validates arguments
- Verify clear error message when database is unreachable
