FROM python:3.12-slim

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
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

# ソースコードのコピー
COPY . .

# データディレクトリの作成
RUN mkdir -p embeddings && \
    mkdir -p .cache/huggingface && \
    chown -R nobody:nogroup embeddings .cache

# 環境変数の設定
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONPATH=/app

# 実行ユーザーの変更
USER nobody

# ポートの公開
EXPOSE 8000

# アプリケーションの実行
CMD ["python", "-m", "src.main"] 
