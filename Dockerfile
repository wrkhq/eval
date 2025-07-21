FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install common Python testing tools
RUN pip install --no-cache-dir \
    pytest \
    pytest-json-report \
    pytest-html \
    coverage \
    tox \
    flake8 \
    black \
    mypy

# Set working directory
WORKDIR /workspace

# Copy test runner script
COPY test_runner.py /usr/local/bin/test_runner.py
RUN chmod +x /usr/local/bin/test_runner.py

# Default command
CMD ["python", "/usr/local/bin/test_runner.py"]
