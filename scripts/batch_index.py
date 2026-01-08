#!/usr/bin/env python3
"""バッチインデクシング - PDFを一括処理"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import sys
import json
import logging
import gc
from pathlib import Path
from typing import Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indexing import IndexBuilder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EMBEDDINGS_DIR = Path("embeddings")
PROCESSED_FILES = EMBEDDINGS_DIR / "processed_files.json"
SAVE_INTERVAL = 5


def load_processed() -> Set[str]:
    if PROCESSED_FILES.exists():
        return set(json.loads(PROCESSED_FILES.read_text(encoding='utf-8')))
    return set()


def save_processed(files: Set[str]) -> None:
    PROCESSED_FILES.write_text(json.dumps(list(files), ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PDFバッチインデクシング")
    parser.add_argument("path", type=Path, help="PDFファイルまたはディレクトリ")
    parser.add_argument("-r", "--recursive", action="store_true", help="サブディレクトリも処理")
    args = parser.parse_args()

    EMBEDDINGS_DIR.mkdir(exist_ok=True)

    logger.info("モデルをロード中...")
    builder = IndexBuilder()
    builder.load()
    logger.info("モデルのロード完了")

    # 整合性チェック
    ok, msg = builder.verify()
    if not ok:
        logger.error(f"データ整合性エラー: {msg}")
        logger.error("embeddings/を削除して再インデックスしてください")
        return

    processed = load_processed()
    logger.info(f"処理済み: {len(processed)}ファイル")

    # PDFリスト
    if args.path.is_file():
        files = [args.path]
    else:
        pattern = "**/*.pdf" if args.recursive else "*.pdf"
        files = sorted(args.path.glob(pattern))

    logger.info(f"対象: {len(files)}ファイル")

    total_files = 0
    total_pages = 0
    skipped = 0

    for i, path in enumerate(files, 1):
        if path.name in processed:
            skipped += 1
            continue

        logger.info(f"[{i}/{len(files)}] {path.name}")
        pages, msg = builder.add_pdf_file(path)

        if pages > 0:
            total_files += 1
            total_pages += pages
            processed.add(path.name)
            logger.info(f"  完了: {pages}ページ")

            if total_files % SAVE_INTERVAL == 0:
                logger.info("保存中...")
                builder.save()
                save_processed(processed)
                gc.collect()
        else:
            logger.warning(f"  スキップ: {msg}")
            processed.add(path.name)
            gc.collect()

    # 最終保存
    logger.info("最終保存中...")
    builder.save()
    save_processed(processed)

    stats = builder.stats
    logger.info("=" * 50)
    logger.info(f"処理完了: {total_files}ファイル, {total_pages}ページ")
    logger.info(f"スキップ: {skipped}ファイル (処理済み)")
    logger.info(f"合計: ベクトル{stats['vectors']}件, メタデータ{stats['metadata']}件")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
