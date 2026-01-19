---
description: PDFをバッチインデックス
---

PDFファイルをインデックスしてください。

```bash
# 単一ファイル
uv run python scripts/batch_index.py document.pdf

# ディレクトリ内の全PDF
uv run python scripts/batch_index.py /path/to/pdfs/

# サブディレクトリも含める（再帰）
uv run python scripts/batch_index.py /path/to/pdfs/ -r
```

進捗は標準出力に表示されます。途中で停止しても、次回実行時に続きから再開されます。

## 最近追加されたファイルを確認
```bash
ls -lt docs/*.pdf | head -5
```
