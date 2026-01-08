---
description: テスト実行
---

検索精度テストを実行してください。

```bash
pytest tests/ -v
```

または検索品質の手動テスト:
```bash
# APIが起動している状態で
curl -s "http://localhost:8000/search?query=機械学習&top_k=3" | python -m json.tool
curl -s "http://localhost:8000/search?query=Elixir&top_k=3" | python -m json.tool
curl -s "http://localhost:8000/search?query=ソフトウェア開発&top_k=3" | python -m json.tool
```
