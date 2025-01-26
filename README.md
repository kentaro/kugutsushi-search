# 詳細仕様書: PDF検索エンジン "kugutsushi-search"

## **1. プロジェクト概要**
本プロジェクトでは、PDFドキュメントを対象にベクトル検索を実現するローカル検索エンジンを開発します。OCR処理済みのPDFからテキストを抽出し、文ベクトルを生成してインデックスを作成、検索クエリに基づいて類似文を高速に検索できるシステムを構築します。

主な用途として、Raspberry Pi上で動作するDiscordボットとn8nを組み合わせたRAGシステムのバックエンドとして機能します。

### **1.1. システム構成**
- Raspberry Pi上で動作するDiscordボットが特定の発言を検知
- n8n上のOpenAIエージェントが発言からクエリを生成
- 本検索エンジンがクエリに基づいて関連文書を検索
- OpenAIエージェントが検索結果を用いてRAGベースの回答を生成
- Discordボットが回答をメッセージとして投稿

### **1.2. プラットフォーム互換性に関する注意事項**
- faissインデックスはプラットフォーム依存のバイナリ形式で保存されます
- インデックスの構築はMac（開発環境）で行い、numpy形式で保存します
- Raspberry Pi上では起動時にnumpyデータからfaissインデックスを自動的に再構築します
- 本番環境はLinux/arm64環境（Raspberry Pi）での実行を前提としています

---

## **2. 要求仕様**

### **2.1. 基本要件**
- PDFファイルは任意のディレクトリから指定可能。
- `PyMuPDF`を用いてPDFテキストを高速に抽出。
- マルチスレッド処理によりPDFの処理を並列化（Apple M3 Max向けに最適化）。
- 文ベクトルは`hotchpotch/static-embedding-japanese`モデルを使用。
- ベクトル検索エンジンは`faiss`を利用。
- 検索機能はCLIコマンドとAPIの2通りで提供。
- ローカル環境（MacBook）で動作確認後、Raspberry Piにデプロイ。

### **2.2. 拡張要件**
- 既に処理済みのPDFファイルは再処理をスキップ。
- 処理の進捗状況をプログレスバーで表示。
- プラットフォーム間でのインデックス互換性のためnumpy形式でデータを保存。

---

## **3. システム設計**

### **3.1. ディレクトリ構造**
```
kugutsushi-search/
├── embeddings/           # ベクトルデータ保存ディレクトリ
├── src/                  # ソースコード
│   ├── extractor.py      # PDF抽出ロジック
│   ├── embedder.py       # 文ベクトル生成ロジック
│   ├── indexer.py        # インデックス構築ロジック
│   ├── api.py            # APIエンドポイント（FastAPI）
│   ├── cli.py            # CLIツール
│   └── main.py          # APIサーバー起動
├── tests/                # テストコード
├── requirements-api.txt  # API用Python依存関係
├── requirements-cli.txt  # CLI用Python依存関係
├── Dockerfile            # Dockerコンテナ設定
└── README.md             # プロジェクト概要
```

### **3.2. モジュール設計**

#### **3.2.1. PDF抽出 (`extractor.py`)**
- `PyMuPDF`を使用してPDF内のテキストをページ単位で抽出。
- マルチスレッド処理により複数ページを並列に処理（デフォルト8スレッド）。
- 抽出テキストはリスト形式で返却。
- 進捗状況を`tqdm`で可視化。

#### **3.2.2. 文ベクトル生成 (`embedder.py`)**
- `hotchpotch/static-embedding-japanese`モデルを使用。
- センテンス単位でベクトルを生成し、NumPy配列として返却。

#### **3.2.3. インデクシング (`indexer.py`)**
- `faiss`を使用してベクトルデータを管理。
- メタデータ（ファイル名、ページ番号）をインデックスと紐付け。
- numpy形式でベクトルデータを保存し、起動時にfaissインデックスを構築。
- 新規ベクトルのみを追加可能。

#### **3.2.4. APIエンドポイント (`api.py`)**
- HTTPリクエストを受けて検索機能を提供。
- PDFのアップロードと検索の2つのエンドポイントを提供。
- クエリパラメータのバリデーションや結果のフォーマットを管理。

#### **3.2.5. CLIツール (`cli.py`)**
- 以下のコマンドを提供:
  - `upload <file>`: PDFファイルをアップロード。
  - `search <query>`: 検索クエリを受け取り、結果を表示。

---

## **4. Docker化とデプロイ**

### **5.1. Docker環境**
- Python 3.10をベースイメージとして使用。
- 必要なシステムライブラリをインストール。
- 依存関係を`requirements-api.txt`から管理。
- `embeddings`ディレクトリをコンテナ内に作成。

### **5.2. デプロイ計画**
1. インデックス構築:
   - Mac上でPDFからテキストを抽出し、ベクトル化
   - numpy形式でベクトルデータを保存
2. Docker化:
   - すべての依存関係をDockerコンテナにまとめる
   - `Dockerfile`を作成し、ローカルで動作確認
3. Raspberry Piへのデプロイ:
   - numpyデータとDockerイメージを転送
   - 起動時にnumpyデータからfaissインデックスを構築

### **5.3. Dockerの実行方法**

#### **5.3.1. イメージのビルド**
```bash
# ローカル開発用（Mac）
docker build -t kugutsushi-search:dev .

# 本番環境用（Raspberry Pi向け）
docker buildx build --platform linux/arm64 -t kugutsushi-search:prod .
```

#### **5.3.2. APIサーバーの起動**
```bash
# Mac（開発環境）での実行 - インデックス構築
docker run --rm \
  -p 8000:8000 \
  -v $(pwd)/embeddings:/app/embeddings \
  kugutsushi-search:dev

# Raspberry Pi（本番環境）での実行 - numpyデータからインデックス再構築
docker run --rm \
  -p 8000:8000 \
  -v $(pwd)/embeddings:/app/embeddings \
  kugutsushi-search:prod
```

注意: 
- ボリュームマウント（`-v`オプション）は必須です。マウントしないと、インデックスデータが失われます。
- インデックスの構築はMac上で行い、numpy形式で保存します。
- Raspberry Pi上では起動時にnumpyデータからfaissインデックスを自動的に再構築します。

#### **5.3.3. CLIクライアントの使用**
```bash
# 依存関係のインストール
pip install -r requirements-cli.txt

# PDFのアップロード
python -m src.cli upload path/to/document.pdf

# テキスト検索
python -m src.cli search "検索クエリ"
```
