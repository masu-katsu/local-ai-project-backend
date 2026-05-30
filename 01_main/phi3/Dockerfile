# ============================================
# Phi3 会話AI（CPU動作）
# ============================================
FROM python:3.11-slim

WORKDIR /app

# llama-cpp-python のビルドに必要なコンパイラとツールをインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    cmake \
    make \
    && rm -rf /var/lib/apt/lists/*

# 依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ビルドツールを削除して軽量化、libgomp（llama-cppの実行に必要）を追加
RUN apt-get purge -y gcc g++ cmake make && \
    apt-get autoremove -y && \
    apt-get update && apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# アプリケーションコピー
COPY app/ ./app/

# ポート公開
EXPOSE 8001

# 起動コマンド
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
