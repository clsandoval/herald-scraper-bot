FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY lambda_function.py .
COPY functions.py .
COPY constants.py .
COPY ability_ids.json .

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app
USER app

# Set the command to run your application
CMD ["python", "lambda_function.py"]