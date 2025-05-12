FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir itsdangerous==2.1.2
RUN pip install --no-cache-dir starlette
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir itsdangerous==2.1.2

# Verify installation
RUN python -c "import itsdangerous; print(f'itsdangerous {itsdangerous.__version__} installed successfully')"
RUN python -c "from starlette.middleware.sessions import SessionMiddleware; print('SessionMiddleware imported successfully')"

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos "" appuser
RUN chown -R appuser:appuser /app
USER appuser

# Make scripts executable
RUN chmod +x start.py

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "start.py", "--no-reload"] 