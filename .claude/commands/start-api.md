---
description: 検索APIを起動
---

検索APIサーバーを起動してください。

```bash
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000
```

起動後、http://localhost:8000/docs でSwagger UIが利用可能です。
