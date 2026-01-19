---
description: インデックス統計を表示
---

現在のインデックス状態を確認してください。

## API経由（APIが起動している場合）
```bash
uv run python src/cli.py status
```

## 直接確認
```bash
uv run python -c "
from src.indexer import Indexer
from src.bm25_indexer import BM25Indexer
indexer = Indexer()
bm25 = BM25Indexer()
indexer.load()
bm25.load()
print(f'ベクトル: {indexer.get_vector_count():,}')
print(f'BM25: {bm25.corpus_size:,}')
print(f'メタデータ: {indexer.db.get_metadata_count():,}')
"
```

## ファイルサイズ確認
```bash
ls -lh embeddings/
```
