FROM python:3.12-slim-bookworm

# Install system deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev libssl-dev libsqlite3-dev sqlite3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application
COPY . /app

# Ensure PYTHONPATH points to app
ENV PYTHONPATH=/app

# Install python requirements if provided
RUN if [ -f /app/requirements.txt ]; then pip install --no-cache-dir -r /app/requirements.txt; fi

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
