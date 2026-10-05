# Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation
# Base image: Official Python 3.10 Slim per Case Study 5 pilot deployment specification
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Set working directory inside container
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code, configuration, data directory, and tests
COPY .streamlit/ ./.streamlit/
COPY src/ ./src/
COPY data/ ./data/
COPY tests/ ./tests/

# Expose ports: 8000 (FastAPI REST backend), 8501 (Streamlit Test Studio UI)
EXPOSE 8000 8501

# Default command: FastAPI REST service (overridden by docker-compose for individual services)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
