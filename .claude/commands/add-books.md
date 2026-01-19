---
description: 書籍追加ワークフロー（インデックス→検証→デプロイ）
---

新しい書籍を追加する一連のワークフローを実行してください。

## 1. 新しいPDFの確認

最近追加されたファイルを確認:
```bash
ls -lt docs/*.pdf | head -10
```

## 2. インデックス作成

新しいPDFをインデックス:
```bash
# 単一ファイル
uv run python scripts/batch_index.py "docs/ファイル名.pdf"

# 複数ファイル（最近追加されたもの全て）
uv run python scripts/batch_index.py docs/ -r
```

## 3. 検証

APIを起動して検索テスト:
```bash
# バックグラウンドでAPI起動
uv run uvicorn src.api:app --host 127.0.0.1 --port 8000 &
sleep 30  # モデル読み込み待機

# 新しく追加した書籍が検索できるか確認
uv run python src/cli.py search "追加した書籍に含まれるキーワード" --top-k 5
```

## 4. デプロイ（オプション）

検証が成功したらRaspberry Piへデプロイ:
```bash
PI_HOST=raspberrypi.local PI_USER=kentaro ./scripts/deploy.sh
```

## 5. デプロイ後の確認

```bash
ssh kentaro@raspberrypi.local 'systemctl status kugutsushi-search'
```
