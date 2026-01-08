#!/bin/bash
# Raspberry Piへのデプロイスクリプト

set -e

# .envファイルがあれば読み込む
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "${SCRIPT_DIR}/../.env" ]; then
    source "${SCRIPT_DIR}/../.env"
fi

# 設定（.envまたは環境変数で上書き可能）
PI_HOST="${PI_HOST:-raspberrypi.local}"
PI_USER="${PI_USER:-pi}"
PI_DIR="${PI_DIR:-/home/${PI_USER}/kugutsushi-search}"

echo "=== kugutsushi-search デプロイ ==="
echo "Target: ${PI_USER}@${PI_HOST}:${PI_DIR}"

# 必要なファイル
FILES=(
    "embeddings/faiss.index"
    "embeddings/index_state.json"
    "embeddings/metadata.db"
    "embeddings/bm25.db"
    "src/"
    "scripts/kugutsushi-search.service"
    "requirements.txt"
)

# ファイル存在確認
echo ""
echo "=== ファイル確認 ==="
for f in "${FILES[@]}"; do
    if [ -e "$f" ]; then
        if [ -f "$f" ]; then
            size=$(du -h "$f" | cut -f1)
            echo "  ✓ $f ($size)"
        else
            echo "  ✓ $f (dir)"
        fi
    else
        echo "  ✗ $f (missing!)"
        exit 1
    fi
done

# 合計サイズ
total=$(du -ch embeddings/*.db embeddings/*.index embeddings/*.json 2>/dev/null | tail -1 | cut -f1)
echo ""
echo "合計: $total"

# 確認
echo ""
read -p "デプロイを続行しますか？ [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "キャンセルしました"
    exit 0
fi

# ディレクトリ作成
echo ""
echo "=== リモートディレクトリ作成 ==="
ssh "${PI_USER}@${PI_HOST}" "mkdir -p ${PI_DIR}/embeddings ${PI_DIR}/src ${PI_DIR}/scripts"

# rsync転送
echo ""
echo "=== ファイル転送中 ==="
rsync -avz --progress \
    embeddings/faiss.index \
    embeddings/index_state.json \
    embeddings/metadata.db \
    embeddings/bm25.db \
    "${PI_USER}@${PI_HOST}:${PI_DIR}/embeddings/"

rsync -avz --progress \
    src/ \
    "${PI_USER}@${PI_HOST}:${PI_DIR}/src/"

rsync -avz --progress \
    requirements.txt \
    "${PI_USER}@${PI_HOST}:${PI_DIR}/"

rsync -avz --progress \
    scripts/kugutsushi-search.service \
    "${PI_USER}@${PI_HOST}:${PI_DIR}/scripts/"

# 検証スクリプト転送・実行
echo ""
echo "=== 動作検証 ==="
ssh "${PI_USER}@${PI_HOST}" "cd ${PI_DIR} && python3 -c \"
import sys
sys.path.insert(0, '.')

print('1. FAISSインデックス読み込み...')
from src.indexer import Indexer
indexer = Indexer()
indexer.load()
print(f'   ベクトル数: {indexer.get_vector_count():,}')

print('2. BM25インデックス読み込み...')
from src.bm25_indexer import BM25Indexer
bm25 = BM25Indexer()
bm25.load()
print(f'   文書数: {bm25.corpus_size:,}')

print('3. 整合性チェック...')
ok, msg = indexer.verify_integrity()
print(f'   {msg}')

if not ok:
    sys.exit(1)

print()
print('✓ デプロイ検証成功！')
\""

# systemdサービス登録・再起動
echo ""
echo "=== systemdサービス設定 ==="

# サービスファイルのパスを環境に合わせて更新
ssh "${PI_USER}@${PI_HOST}" "
    # サービスファイルをコピー（sudoが必要）
    sudo cp ${PI_DIR}/scripts/kugutsushi-search.service /etc/systemd/system/

    # サービスファイル内のパスを実際の環境に合わせて置換
    sudo sed -i 's|/home/kentaro|/home/${PI_USER}|g' /etc/systemd/system/kugutsushi-search.service
    sudo sed -i 's|User=kentaro|User=${PI_USER}|g' /etc/systemd/system/kugutsushi-search.service
    sudo sed -i 's|Group=kentaro|Group=${PI_USER}|g' /etc/systemd/system/kugutsushi-search.service

    # systemd再読み込み・有効化・再起動
    sudo systemctl daemon-reload
    sudo systemctl enable kugutsushi-search
    sudo systemctl restart kugutsushi-search

    # 起動確認
    sleep 2
    sudo systemctl status kugutsushi-search --no-pager || true
"

echo ""
echo "=== デプロイ完了 ==="
echo ""
echo "サービス状態確認:"
echo "  ssh ${PI_USER}@${PI_HOST} 'systemctl status kugutsushi-search'"
echo ""
echo "ログ確認:"
echo "  ssh ${PI_USER}@${PI_HOST} 'journalctl -u kugutsushi-search -f'"
