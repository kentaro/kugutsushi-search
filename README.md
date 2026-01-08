# kugutsushi-search

PDF文書のハイブリッド検索エンジン。Raspberry Pi 4B (4GB RAM) での動作を想定。

## 特徴

- **ハイブリッド検索**: ベクトル検索 + BM25 + Cross-Encoder リランキング
- **日本語最適化**: Ruri v3-130m + japanese-reranker-tiny
- **高速検索**: FAISS IVF-PQ インデックス（100万ベクトルで ~40ms）
- **軽量設計**: SQLite ベースのメタデータ・BM25 インデックス
- **中断再開**: チェックポイント機能で途中から再開可能

## パフォーマンス

100万ベクトル（1,400+ PDF）での実測値:

| 検索モード | 平均レイテンシ |
|-----------|---------------|
| Vector Only | 36ms |
| Hybrid (Vector + BM25) | 450ms |
| Hybrid + Rerank | 630ms |

## インストール

```bash
# 依存関係
pip install -r requirements.txt

# 開発用（pytest含む）
pip install -r requirements-dev.txt
```

## 使い方

### インデックス構築

```bash
# 単一ファイル
python scripts/batch_index.py document.pdf

# ディレクトリ（再帰）
python scripts/batch_index.py /path/to/pdfs -r
```

### API サーバー起動

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

### 検索

```bash
curl "http://localhost:8000/search?query=機械学習&top_k=5"
```

## API

| エンドポイント | 説明 |
|---------------|------|
| `GET /search?query=...&top_k=5&mode=hybrid+rerank` | 検索 |
| `GET /status` | システム状態 |
| `POST /upload` | PDF追加 |

### 検索モード

- `hybrid`: ベクトル + BM25（高速）
- `hybrid+rerank`: ベクトル + BM25 + リランキング（高精度）

## Raspberry Pi へのデプロイ

### 方法1: ネイティブ Python（推奨、4GB RAM向け）

```bash
# Pi側でセットアップ
./scripts/setup_pi.sh

# Mac側からデプロイ
PI_HOST=raspberrypi.local PI_USER=pi ./scripts/deploy.sh
```

### 方法2: Docker

```bash
# ビルド + デプロイ
./scripts/deploy-docker.sh --all
```

### systemd サービス

デプロイスクリプトが自動的にsystemdサービスを登録・起動します。

```bash
# 状態確認
systemctl status kugutsushi-search

# ログ確認
journalctl -u kugutsushi-search -f
```

### メモリ制約

Raspberry Pi 4GB では、リランキングを無効化することを推奨:

```bash
curl "http://localhost:8000/search?query=...&mode=hybrid"
```

## ファイル構成

```
src/
├── api.py           # FastAPI サーバー
├── embedder.py      # Ruri v3 埋め込み生成
├── indexer.py       # FAISS ベクトルインデックス
├── bm25_indexer.py  # SQLite BM25 インデックス
├── hybrid_searcher.py # ハイブリッド検索 + RRF
├── reranker.py      # Cross-Encoder リランキング
├── extractor.py     # PDF テキスト抽出・チャンキング
├── database.py      # SQLite メタデータ管理
├── indexing.py      # インデックス構築ライブラリ
└── text_filter.py   # 低品質ページフィルタ

scripts/
├── batch_index.py   # バッチインデックス構築
├── evaluate.py      # 評価スクリプト
├── deploy.sh        # ネイティブデプロイ
├── deploy-docker.sh # Docker デプロイ
├── setup_pi.sh      # Pi セットアップ
├── dev.sh           # 開発サーバー
└── kugutsushi-search.service  # systemd ユニットファイル

embeddings/          # インデックスデータ（gitignore）
├── faiss.index      # FAISS バイナリ
├── metadata.db      # メタデータ (SQLite)
├── bm25.db          # BM25 インデックス (SQLite)
└── index_state.json # 訓練状態
```

## テスト

```bash
pytest tests/ -v
```

## 技術詳細

### ベクトル検索

- モデル: [cl-nagoya/ruri-v3-130m](https://huggingface.co/cl-nagoya/ruri-v3-130m)
- 次元: 512
- インデックス: FAISS IVF256,PQ16,RFlat

### BM25

- SQLite + バイナリ BLOB ストレージ
- 2-gram トークナイズ
- 語彙削減（低頻度語除外）

### リランキング

- モデル: [hotchpotch/japanese-reranker-tiny-v2](https://huggingface.co/hotchpotch/japanese-reranker-tiny-v2)
- RRF スコアとブレンド

## ライセンス

MIT
