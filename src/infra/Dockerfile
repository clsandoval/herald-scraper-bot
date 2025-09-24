FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv for dependency management
RUN apt-get update && apt-get install -y \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Add uv to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies using uv
RUN uv sync --frozen --no-cache

# Copy the source code
COPY src/ ./src/
COPY .env* ./

# Create logs directory
RUN mkdir -p logs

# Run the bot using uv
CMD ["uv", "run", "python", "-m", "src.main"]
