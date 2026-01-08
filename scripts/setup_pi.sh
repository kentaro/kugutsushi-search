#!/bin/bash
# Raspberry Pi セットアップスクリプト
# Pi上で実行してください

set -e

echo "=== kugutsushi-search Raspberry Pi セットアップ ==="
echo ""

# Python確認
python_version=$(python3 --version 2>&1)
echo "Python: $python_version"

# 仮想環境作成
if [ ! -d "venv" ]; then
    echo ""
    echo "=== 仮想環境作成 ==="
    python3 -m venv venv
fi

source venv/bin/activate

# pip更新
echo ""
echo "=== pip更新 ==="
pip install --upgrade pip wheel

# PyTorch (ARM用)
echo ""
echo "=== PyTorch インストール ==="
# Raspberry Pi 4 (aarch64) 用
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# FAISS (重要: バージョン固定)
echo ""
echo "=== FAISS インストール ==="
pip install faiss-cpu==1.8.0

# その他の依存関係
echo ""
echo "=== 依存関係インストール ==="
pip install \
    sentence-transformers>=3.4.0 \
    transformers>=4.48.0 \
    fastapi==0.110.0 \
    uvicorn==0.27.1 \
    numpy>=1.26.4,<2.0 \
    tqdm==4.66.2

# Embeddingモデルを事前ダウンロード
echo ""
echo "=== Embeddingモデルダウンロード ==="
python3 -c "
from sentence_transformers import SentenceTransformer
print('Downloading cl-nagoya/ruri-v3-130m...')
model = SentenceTransformer('cl-nagoya/ruri-v3-130m')
print('Done!')
"

# 検証
echo ""
echo "=== インストール検証 ==="
python3 -c "
import torch
import faiss
import sentence_transformers
print(f'PyTorch: {torch.__version__}')
print(f'FAISS: {faiss.__version__ if hasattr(faiss, \"__version__\") else \"1.8.0\"}')
print(f'SentenceTransformers: {sentence_transformers.__version__}')
"

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "  1. Mac側でデプロイ実行: ./scripts/deploy.sh"
echo "  2. Pi側でAPI起動:"
echo "     source venv/bin/activate"
echo "     python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000"
