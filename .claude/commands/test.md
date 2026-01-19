---
description: テスト実行
---

検索精度テストを実行してください。

```bash
uv run pytest tests/ -v
```

または検索品質の手動テスト（APIが起動している状態で）:
```bash
uv run python src/cli.py search "機械学習" --top-k 3
uv run python src/cli.py search "Elixir" --top-k 3
uv run python src/cli.py search "ソフトウェア開発" --top-k 3
```
