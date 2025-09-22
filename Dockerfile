# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install uv and dependencies
RUN pip install uv && \
    uv venv && \
    uv sync --no-dev

# Copy application code
COPY src/ ./src/

# Create logs directory
RUN mkdir -p logs

# Set environment to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Run the bot
CMD ["python", "-m", "src.main"]