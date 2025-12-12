# Code Conventions

## Style
- **Python version**: 3.11+
- **Line length**: 100 characters (ruff)
- **Logging**: Use `structlog` with event names like `module.action`
- **Async-first**: All DB operations and external API calls are async
- **Type hints**: Required (mypy strict mode)

## Configuration
- Settings via `pydantic-settings` in `src/infra/config/settings.py`
- SQLModel for database models with async SQLAlchemy

## Tools
- **Linting/Formatting**: ruff
- **Type checking**: mypy with strict options
- **Testing**: pytest with pytest-asyncio

## Patterns
- Use dataclasses for simple data structures
- Use Pydantic models for API request/response
- Use SQLModel for database models
- Async context managers for resource handling
