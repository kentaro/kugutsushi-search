FROM python:3.12-slim as builder

# ビルド用の依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# 仮想環境を作成
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 依存関係をインストール
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# 実行用のステージ
FROM python:3.12-slim

# 仮想環境をコピー
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# アプリケーションのディレクトリを作成
WORKDIR /app

# アプリケーションのコードをコピー
COPY . .

# embeddingsディレクトリを作成
RUN mkdir -p embeddings/.cache
ENV HF_HOME=/app/.cache/huggingface

# ポートを公開
EXPOSE 8000

# アプリケーションを実行
CMD ["python", "-m", "src.main"] 
