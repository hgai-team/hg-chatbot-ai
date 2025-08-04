# Dockerfile v1

# # --- Builder stage: cài tất cả dependencies vào /install ---
# FROM python:3.10.16-slim AS builder
# WORKDIR /app

# # Cài build tools chỉ cho giai đoạn builder
# RUN apt-get update \
#  && apt-get install -y --no-install-recommends \
#       build-essential gcc libssl-dev libffi-dev libpq-dev python3-dev libpq5 \
#  && rm -rf /var/lib/apt/lists/*

# # Copy file requirements và cài với --prefix để có cả /install/bin và /install/lib
# COPY requirements.txt .
# RUN pip install --upgrade pip \
#  && pip install --no-cache-dir \
#       --disable-pip-version-check \
#       --prefix /install \
#       -r requirements.txt

# # --- Runtime stage: chỉ copy /install, code mount bằng volume ---
# FROM python:3.10.16-slim AS runtime
# WORKDIR /app

# # Giữ các thiết lập Python tối ưu
# ENV PIP_NO_CACHE_DIR=1 \
#     PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1

# # Thêm uvicorn và console_scripts vào PATH
# ENV PATH=/install/bin:$PATH
# # Cho Python tìm các package đã cài
# ENV PYTHONPATH=/install/lib/python3.10/site-packages

# # Copy toàn bộ thư mục /install từ builder
# COPY --from=builder /install /install

# Dockerfile v2

# Dockerfile.k8s - Optimized for Kubernetes deployment
# Multi-stage build để giảm size và bảo mật

# --- Stage 1: Builder ---
FROM python:3.10.16-slim AS builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy và install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.10.16-slim AS runtime
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages từ builder
COPY --from=builder /root/.local /root/.local

# Set Python environment
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application code
COPY app/ /app/

# Create necessary directories
RUN mkdir -p /app/uploaded_files /app/logs /app/model_cache && \
    chmod -R 755 /app

# Create non-root user (optional for security)
# RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
# USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
     CMD curl -f http://localhost:8888/api/v1/health || exit 1

# Expose port
EXPOSE 8888

# Run application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]