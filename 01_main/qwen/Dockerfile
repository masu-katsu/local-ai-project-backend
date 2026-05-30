FROM python:3.11-slim

WORKDIR /app

# Build dependencies for llama-cpp-python (CUDA wheel)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ cmake make && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install llama-cpp-python with pre-built CUDA 12.1 wheel (no local CUDA needed)
RUN pip install --no-cache-dir llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121 && \
    pip install --no-cache-dir -r requirements.txt

# Remove build tools, add libgomp (required by llama-cpp at runtime)
RUN apt-get purge -y gcc g++ cmake make && \
    apt-get autoremove -y && \
    apt-get update && apt-get install -y --no-install-recommends libgomp1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
