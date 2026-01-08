"""API サーバー - FastAPIによる検索エンドポイント"""

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import json
import logging
from pathlib import Path

from .indexing import IndexBuilder
from .hybrid_searcher import HybridSearcher, SearchConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EMBEDDINGS_DIR = Path("embeddings")
PROCESSED_FILES_PATH = EMBEDDINGS_DIR / "processed_files.json"
EMBEDDINGS_DIR.mkdir(exist_ok=True)

# 初期化
logger.info("モデルをロード中...")
builder = IndexBuilder()
builder.load()
hybrid_searcher = HybridSearcher(builder.embedder, builder.indexer, builder.bm25)

ok, msg = builder.verify()
if not ok:
    logger.error(f"データ整合性エラー: {msg}")
else:
    logger.info(f"データ整合性OK: {msg}")

logger.info("モデルのロード完了")

app = FastAPI(title="Kugutsushi Search API", version="1.0.0")


class SearchResult(BaseModel):
    text: str
    score: float
    file: str
    page: int


class SearchResponse(BaseModel):
    results: List[SearchResult]


def load_processed_files() -> set:
    if PROCESSED_FILES_PATH.exists():
        return set(json.loads(PROCESSED_FILES_PATH.read_text(encoding='utf-8')))
    return set()


def save_processed_files(files: set) -> None:
    PROCESSED_FILES_PATH.write_text(json.dumps(list(files), ensure_ascii=False, indent=2), encoding='utf-8')


processed_files = load_processed_files()


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """PDFをアップロードしてインデックスに追加"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "PDFファイルのみ対応")

    if file.filename in processed_files:
        raise HTTPException(400, f"{file.filename}は処理済み")

    content = await file.read()
    logger.info(f"PDF処理開始: {file.filename}")

    pages, msg = builder.add_pdf(content, file.filename)

    if pages == 0:
        raise HTTPException(400, msg)

    builder.save()
    processed_files.add(file.filename)
    save_processed_files(processed_files)

    return {"message": f"{file.filename}を処理しました", "texts_count": pages}


@app.get("/search", response_model=SearchResponse)
async def search(
    query: str,
    top_k: Optional[int] = Query(3, ge=1, le=100),
    mode: Optional[str] = Query("hybrid+rerank", regex="^(hybrid|hybrid\\+rerank)$"),
):
    """ハイブリッド検索"""
    try:
        config = SearchConfig(use_bm25=True, use_rerank=(mode == "hybrid+rerank"))
        results = hybrid_searcher.search(query, top_k, config)

        return SearchResponse(results=[
            SearchResult(text=m["text"], score=float(s), file=m["file"], page=m["page"])
            for m, s in results
        ])
    except Exception as e:
        logger.error(f"検索エラー: {e}")
        raise HTTPException(500, str(e))


@app.get("/status")
async def status():
    """システム状態"""
    ok, msg = builder.verify()
    stats = builder.stats
    return {
        "integrity": ok,
        "message": msg,
        "vectors": stats["vectors"],
        "metadata": stats["metadata"],
        "bm25": stats["bm25"],
        "processed_files": len(processed_files)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

