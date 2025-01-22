FROM python:3.12-slim

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# アプリケーションのディレクトリを作成
WORKDIR /app

# 依存関係をインストール
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# アプリケーションのコードをコピー
COPY . .

# embeddingsディレクトリを作成
RUN mkdir -p embeddings/.cache
ENV HF_HOME=/app/.cache/huggingface

# ポートを公開
EXPOSE 8000

# アプリケーションを実行
CMD ["python", "-m", "src.main"] 
