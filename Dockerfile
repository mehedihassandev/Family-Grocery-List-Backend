FROM python:3.11-slim

WORKDIR /app

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy application source code
COPY app ./app

# Expose server port
EXPOSE 8000

# Start FastAPI server on port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
