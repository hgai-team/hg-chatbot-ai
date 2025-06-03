# FROM python:3.10.16-slim

# USER root

# WORKDIR /app

# COPY requirements.txt .

# RUN pip install -r requirements.txt

# --- Builder stage: cài tất cả dependencies vào /install ---
FROM python:3.10.16-slim AS builder
WORKDIR /app

# Cài build tools chỉ cho giai đoạn builder
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential gcc libssl-dev libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy file requirements và cài với --prefix để có cả /install/bin và /install/lib
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir \
      --disable-pip-version-check \
      --prefix /install \
      -r requirements.txt

# --- Runtime stage: chỉ copy /install, code mount bằng volume ---
FROM python:3.10.16-slim AS runtime
WORKDIR /app

# Giữ các thiết lập Python tối ưu
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Thêm uvicorn và console_scripts vào PATH
ENV PATH=/install/bin:$PATH
# Cho Python tìm các package đã cài
ENV PYTHONPATH=/install/lib/python3.10/site-packages

# Copy toàn bộ thư mục /install từ builder
COPY --from=builder /install /install
