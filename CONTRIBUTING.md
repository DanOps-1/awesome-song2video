# Contributing to Song2Video

First off, thank you for considering contributing to Song2Video! It's people like you that make Song2Video such a great tool.

## Code of Conduct

By participating in this project, you are expected to uphold our Code of Conduct: be respectful, inclusive, and constructive.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** (audio files, lyrics, etc.)
- **Describe the behavior you observed and what you expected**
- **Include logs** from `logs/` directory if applicable
- **Include your environment details** (OS, Python version, Node version)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the suggested enhancement**
- **Explain why this enhancement would be useful**
- **List any alternative solutions you've considered**

### Pull Requests

1. **Fork the repo** and create your branch from `main`
2. **Follow the coding style** of the project
3. **Add tests** for any new functionality
4. **Ensure all tests pass** before submitting
5. **Update documentation** if needed
6. **Write a clear PR description**

## Development Setup

### Prerequisites

- Python >= 3.11
- Node.js >= 18
- FFmpeg
- Redis
- PostgreSQL

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/awesome-song2video.git
cd awesome-song2video

# Install Python dependencies
uv sync

# Install frontend dependencies
cd apps/frontend && npm install
cd ../web && npm install
cd ../..

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Start services
bash start.sh
```

### Running Tests

```bash
# Python tests
uv run pytest tests/

# Type checking
uv run mypy src

# Linting
uv run ruff check src tests
uv run ruff format src tests

# Frontend type checking
cd apps/frontend && npx tsc --noEmit
cd apps/web && npx tsc --noEmit
```

### Pre-commit Checklist

Before submitting a PR, ensure:

```bash
# All checks must pass
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run mypy src && \
(cd apps/frontend && npx vite build) && \
(cd apps/web && npx vite build) && \
uv run pytest tests/
```

## Coding Guidelines

### Python

- Follow PEP 8 style guide (enforced by Ruff)
- Use type hints for all function signatures
- Use `structlog` for logging with event names like `module.action`
- Async-first: All DB operations and external API calls should be async
- Write docstrings for public functions (Chinese or English)

### TypeScript/React

- Use TypeScript strict mode
- Use functional components with hooks
- Follow the existing component structure
- Use TailwindCSS for styling

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new lyrics source
fix: resolve audio sync issue
docs: update API documentation
refactor: simplify timeline builder
test: add integration tests for render worker
chore: update dependencies
```

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

## Project Structure

```
src/
├── api/           # FastAPI routes
├── audio/         # Audio processing
├── domain/        # Domain models
├── infra/         # Infrastructure (DB, config)
├── lyrics/        # Lyrics fetching
├── pipelines/     # Processing pipelines
├── services/      # Business logic
├── video/         # Video processing
└── workers/       # Background workers

apps/
├── frontend/      # User-facing React app
└── web/           # Admin dashboard

tests/
├── contract/      # API contract tests
├── integration/   # Integration tests
└── unit/          # Unit tests
```

## Getting Help

- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For questions and general discussion
- **Email**: 870657960@qq.com

## Recognition

Contributors will be recognized in:
- The project README
- Release notes for significant contributions

Thank you for contributing! 🎉
