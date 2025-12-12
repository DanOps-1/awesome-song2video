# Task Completion Checklist

When a task is completed, run these commands:

## Required
```bash
# Lint check
ruff check src tests

# Format code
ruff format src tests

# Type check
mypy src
```

## Optional (if tests exist for the area)
```bash
# Run tests
pytest tests/
```

## Before Commit
1. Ensure all lint errors are fixed
2. Ensure type errors are resolved
3. Ensure tests pass (if applicable)
