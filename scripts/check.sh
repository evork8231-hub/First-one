#!/usr/bin/env bash
# Runs the full local quality gate: lint, format check, type check, tests.
# Mirrors what CI (and pre-commit) enforce -- run this before every commit.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> ruff (lint)"
ruff check app tests alembic

echo "==> black (format check)"
black --check app tests alembic

echo "==> mypy (type check)"
mypy app

echo "==> pytest (unit tests + coverage)"
pytest

echo "All checks passed."
