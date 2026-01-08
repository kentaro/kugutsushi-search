---
description: Raspberry Piへデプロイ
---

Raspberry Pi 4Bへデプロイしてください。

## 方法1: ネイティブPython（推奨、4GB RAM向け）

```bash
# Pi側で初回セットアップ
./scripts/setup_pi.sh

# Mac側からデプロイ
PI_HOST=raspberrypi.local PI_USER=pi ./scripts/deploy.sh
```

## 方法2: Docker

```bash
# ビルド + デプロイ
./scripts/deploy-docker.sh --all

# または個別に
./scripts/deploy-docker.sh --build      # イメージビルド
./scripts/deploy-docker.sh --embeddings # embeddingsのみ転送
./scripts/deploy-docker.sh --deploy     # デプロイのみ
```

## デプロイ後

デプロイスクリプトがsystemdサービスを自動登録・起動します。

### 状態確認
```bash
ssh pi@raspberrypi 'systemctl status kugutsushi-search'
```

### ログ確認
```bash
ssh pi@raspberrypi 'journalctl -u kugutsushi-search -f'
```

### 手動起動（デバッグ用）
```bash
ssh pi@raspberrypi
sudo systemctl stop kugutsushi-search
cd ~/kugutsushi-search
source venv/bin/activate
uvicorn src.api:app --host 0.0.0.0 --port 8000
```
