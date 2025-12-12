# Suggested Commands

## Development
```bash
# Start all services (backend + frontends)
bash start.sh

# Start backend API only (port 8000)
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Start workers
python -m src.workers.render_worker    # Video rendering worker
python -m src.workers.timeline_worker  # Timeline generation worker

# Start frontends
cd frontend && npm run dev -- --port 6008  # User frontend
cd web && npm run dev -- --port 6006       # Admin dashboard
```

## Testing
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/contract/test_health.py

# Run e2e tests
python scripts/dev/e2e_full_render_test.py
```

## Code Quality
```bash
# Lint and format
ruff check src tests
ruff format src tests

# Type checking
mypy src
```

## Utility Commands
```bash
# List files
ls -la

# Find files
find . -name "*.py"

# Search in files
grep -r "pattern" src/
```
