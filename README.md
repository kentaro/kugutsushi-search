# 詳細仕様書: PDF検索エンジン "kugutsushi-search"

## **1. プロジェクト概要**
本プロジェクトでは、PDFドキュメントを対象にベクトル検索を実現するローカル検索エンジンを開発します。OCR処理済みのPDFからテキストを抽出し、文ベクトルを生成してインデックスを作成、検索クエリに基づいて類似文を高速に検索できるシステムを構築します。

---

## **2. 要求仕様**

### **2.1. 基本要件**
- PDFファイルは任意のディレクトリから指定可能。
- `pdfplumber`を用いてPDFテキストを抽出。
- 文ベクトルは`hotchpotch/static-embedding-japanese`モデルを使用。
- ベクトル検索エンジンは`faiss`を利用。
- 検索機能はCLIコマンドとAPIの2通りで提供。
- ローカル環境（MacBook）で動作確認後、Google Cloudにコンテナとしてデプロイ可能。

### **2.2. 拡張要件**
- 検索結果にクエリ一致箇所の文脈をハイライト表示。
- 既に処理済みのPDFファイルは再処理をスキップ。

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
- `pdfplumber`を使用してPDF内のテキストをページ単位で抽出。
- 抽出テキストはリスト形式で返却。

#### **3.2.2. 文ベクトル生成 (`embedder.py`)**
- `hotchpotch/static-embedding-japanese`モデルを使用。
- センテンス単位でベクトルを生成し、NumPy配列として返却。

#### **3.2.3. インデクシング (`indexer.py`)**
- `faiss`を使用してベクトルデータを管理。
- メタデータ（ファイル名、ページ番号）をインデックスと紐付け。
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

## **4. 検索結果ハイライト**

### **4.1. 概要**
検索クエリと一致するテキスト部分を強調表示し、その前後の文脈を提供。

### **4.2. 実装例**
- 正規表現を使用してクエリと一致する箇所を検出。
- 一致部分を`**`で囲み、文脈とともにリスト形式で返却。

---

## **5. Docker化とデプロイ**

### **5.1. Docker環境**
- Python 3.10をベースイメージとして使用。
- 必要なシステムライブラリをインストール。
- 依存関係を`requirements-api.txt`から管理。
- `embeddings`ディレクトリをコンテナ内に作成。

### **5.2. デプロイ計画**
1. Docker化:
   - すべての依存関係をDockerコンテナにまとめる。
   - `Dockerfile`を作成し、ローカルで動作確認。
2. Google Cloudへの移行:
   - DockerイメージをGoogle Container Registry (GCR) にアップロード。
   - Google Cloud Runにデプロイしてスケーラブルな運用を実現。

### **5.3. Dockerの実行方法**

#### **5.3.1. イメージのビルド**
```bash
docker build -t kugutsushi-search .
```

#### **5.3.2. APIサーバーの起動**
```bash
# 重要: embeddingsディレクトリをマウントして起動
docker run --rm -p 8000:8000 -v $(pwd)/embeddings:/app/embeddings kugutsushi-search
```

注意: ボリュームマウント（`-v`オプション）は必須です。マウントしないと、コンテナ停止時にインデックスデータが失われます。

#### **5.3.3. CLIクライアントの使用**
```bash
# 依存関係のインストール
pip install -r requirements-cli.txt

# PDFのアップロード
python -m src.cli upload path/to/document.pdf

# テキスト検索
python -m src.cli search "検索クエリ"
```
