---
description: 検索テスト実行
---

$ARGUMENTSをクエリとして検索APIに問い合わせてください。

```bash
uv run python src/cli.py search "$ARGUMENTS" --top-k 5
```

APIが起動していない場合は先に `/start-api` を実行してください。
