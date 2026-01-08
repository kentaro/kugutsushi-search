---
description: 検索テスト実行
---

$ARGUMENTSをクエリとして検索APIに問い合わせてください。

```bash
curl -s "http://localhost:8000/search?query=$ARGUMENTS&top_k=5" | python -m json.tool
```

APIが起動していない場合は先に `/start-api` を実行してください。
