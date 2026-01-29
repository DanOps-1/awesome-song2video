## Description

<!-- Describe your changes in detail -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Refactoring (no functional changes)
- [ ] 🧪 Test update

## Related Issues

<!-- Link any related issues here -->

Fixes #

## Checklist

<!-- Mark completed items with an "x" -->

- [ ] My code follows the project's coding style
- [ ] I have performed a self-review of my code
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing tests pass locally
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings

## Pre-commit Verification

<!-- Confirm all checks pass -->

```bash
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy src
cd apps/frontend && npx vite build
cd apps/web && npx vite build
uv run pytest tests/
```

- [ ] All checks pass ✅

## Screenshots (if applicable)

<!-- Add screenshots to help explain your changes -->

## Additional Notes

<!-- Any additional information that reviewers should know -->
