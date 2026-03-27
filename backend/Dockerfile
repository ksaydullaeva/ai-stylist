# StyleAI backend — FastAPI + uvicorn on GPU (CUDA 12.8, Python 3.12)
# Final stage has Python + CUDA so the app can use the GPU.
FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04

WORKDIR /app

# Python 3.12 + system deps (libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Use a venv so we don't need --break-system-packages (PEP 668)
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install PyTorch with CUDA first (cu124 is compatible with CUDA 12.8 runtime)
RUN pip install --no-cache-dir \
    torch==2.5.1 \
    torchvision==0.20.1 \
    --index-url https://download.pytorch.org/whl/cu124

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure CUDA torch is used (requirements.txt may pull CPU torch)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu124 --upgrade --force-reinstall

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
