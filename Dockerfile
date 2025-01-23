FROM python:3.12-slim AS builder

# ビルドに必要なパッケージのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピー
COPY requirements-api.txt requirements-api.txt
COPY requirements-cli.txt requirements-cli.txt

# 仮想環境の作成とパッケージのインストール
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 依存関係のインストール
RUN pip install --no-cache-dir -r requirements-api.txt

# 実行用ステージ
FROM python:3.12-slim

# 実行に必要なパッケージのインストール
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# 仮想環境のコピー
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 作業ディレクトリの設定
WORKDIR /app

# ソースコードのコピー
COPY . .

# データディレクトリとキャッシュディレクトリの作成
RUN mkdir -p embeddings && \
    mkdir -p /home/nobody/.cache/huggingface && \
    chown -R nobody:nogroup /app /home/nobody && \
    chmod -R 755 /app /home/nobody

# 環境変数の設定
ENV PYTHONPATH=/app
ENV HOME=/home/nobody

# 実行ユーザーの変更
USER nobody

# ポートの公開
EXPOSE 8000

# アプリケーションの実行
CMD ["python", "-m", "src.main"] 
