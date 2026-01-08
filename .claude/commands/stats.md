---
description: インデックス統計を表示
---

現在のインデックス状態を確認してください。

```bash
curl -s "http://localhost:8000/status" | python -m json.tool
```

または直接確認:
```bash
python -c "
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
