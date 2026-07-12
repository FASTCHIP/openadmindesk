# Multi-stage build for OpenAdminDesk
FROM python:3.12-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install poetry
RUN pip install poetry

# Configure poetry
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --only=main

# Production stage
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY pyproject.toml poetry.lock ./

# Install development dependencies for testing
RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --with dev

# Create non-root user
RUN useradd -m -u 1000 openadmindesk
USER openadmindesk

# Expose port (if needed for future web interface)
EXPOSE 8080

# Default command
CMD ["openadmindesk"]