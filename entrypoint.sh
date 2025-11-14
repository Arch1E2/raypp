#!/bin/bash
set -e

# Optionally run tests
if [ "${SKIP_TESTS:-0}" != "1" ]; then
  echo "Running tests..."
  python -m pytest -q || true
fi

# Start the app
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
