---
description: Raspberry Piへデプロイ
---

Raspberry Pi 4Bへデプロイしてください。

## 設定

`.env`ファイルに設定があります：
- `PI_HOST=raspberrypi.local`
- `PI_USER=kentaro`
- `PI_DIR=/home/kentaro/src/github.com/kentaro/kugutsushi-search`

## デプロイ実行

```bash
# 確認プロンプトあり
./scripts/deploy.sh

# 確認プロンプトをスキップ（自動承認）
./scripts/deploy.sh -y
```

## デプロイ後

デプロイスクリプトがsystemdサービスを自動登録・起動します。

### 状態確認
```bash
ssh kentaro@raspberrypi.local 'systemctl status kugutsushi-search'
```

### ログ確認
```bash
ssh kentaro@raspberrypi.local 'journalctl -u kugutsushi-search -f'
```

### 手動起動（デバッグ用）
```bash
ssh kentaro@raspberrypi.local
sudo systemctl stop kugutsushi-search
cd ~/src/github.com/kentaro/kugutsushi-search
source venv/bin/activate
uvicorn src.api:app --host 0.0.0.0 --port 8000
```
