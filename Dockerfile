# Use an official Python runtime as the base image
FROM python:3.13.2-slim-bookworm

# Set working directory in the container
WORKDIR /usr/src/app

# Copy requirements.txt
COPY requirements.txt .

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies in the virtual environment
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy main.py & timezone_cluster_analyzer.py
COPY src/* src/

# Command to run your application
CMD ["python", "src/main.py"]