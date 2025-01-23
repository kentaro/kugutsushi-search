from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import logging
from pathlib import Path
import io
import numpy as np
import faiss

from src.embedder import Embedder
from src.indexer import Indexer
from src.extractor import extract_from_pdf

# ロギング設定
logger = logging.getLogger(__name__)

# 定数
EMBEDDINGS_DIR = Path("embeddings")
PROCESSED_FILES_PATH = EMBEDDINGS_DIR / "processed_files.json"
EMBEDDINGS_DIR.mkdir(exist_ok=True)

# モデルの初期化
logger.info("モデルのロードを開始")
embedder = Embedder()
indexer = Indexer()
indexer.load()  # 保存されているインデックスを読み込む
logger.info("モデルのロードが完了")

# FastAPIアプリケーション
app = FastAPI(
    title="Kugutsushi Search API",
    description="PDF文書の検索APIサーバー",
    version="0.1.0"
)

# モデル定義
class SearchResult(BaseModel):
    text: str
    score: float
    file: str
    page: int

class SearchResponse(BaseModel):
    results: List[SearchResult]

# ユーティリティ関数
def load_processed_files() -> set:
    if PROCESSED_FILES_PATH.exists():
        return set(json.loads(PROCESSED_FILES_PATH.read_text(encoding='utf-8')))
    return set()

def save_processed_files(files: set) -> None:
    PROCESSED_FILES_PATH.write_text(
        json.dumps(list(files), ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

# グローバル変数
processed_files = load_processed_files()

async def process_pdf_content(content: bytes, filename: str) -> int:
    """PDFの内容を処理してインデックスに追加する"""
    logger.info(f"=== PDFの処理を開始: {filename} ===")
    logger.info(f"ファイルサイズ: {len(content) / 1024 / 1024:.2f}MB")
    
    try:
        # PDFからテキストを抽出
        logger.info("テキスト抽出を開始")
        pdf_bytes = io.BytesIO(content)
        texts = extract_from_pdf(pdf_bytes.getvalue())
        logger.info(f"テキスト抽出完了: {len(texts)}ページ")
        
        # 空のページをスキップ
        texts = [
            {
                "text": text["text"].strip(),
                "page": text["page"]
            }
            for text in texts
            if len(text["text"].strip()) > 0
        ]
        
        # ベクトルとメタデータを生成
        logger.info("ベクトル生成を開始")
        vectors = []
        metadata = []
        for i, text in enumerate(texts, 1):
            vector = embedder.generate_embedding(text["text"])
            vectors.append(vector)
            metadata.append({
                "text": text["text"],
                "file": filename,
                "page": text["page"] - 1
            })
            if i % 10 == 0:  # 10ページごとに進捗を表示
                logger.info(f"進捗: {i}/{len(texts)} ページ完了 ({i/len(texts)*100:.1f}%)")
        
        logger.info(f"ベクトル生成完了: {len(vectors)}件")
        
        # インデックスに追加して保存
        logger.info("インデックスへの追加を開始")
        vectors_np = np.array(vectors, dtype=np.float32)
        indexer.add(vectors_np, metadata)
        logger.info(f"インデックスに{len(vectors)}件追加完了")
        
        logger.info("インデックスの保存を開始")
        indexer.save()
        logger.info("インデックスの保存完了")
        
        return len(texts)
        
    except Exception as e:
        logger.error(f"=== エラー発生: {filename} ===")
        logger.error(f"エラーの種類: {type(e).__name__}")
        logger.error(f"エラーメッセージ: {str(e)}")
        logger.error("詳細なスタックトレース:", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PDF処理エラー",
                "file": filename,
                "message": str(e),
                "type": type(e).__name__
            }
        )

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """PDFファイルをアップロードして処理する"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDFファイルのみアップロード可能です")
    
    if file.filename in processed_files:
        raise HTTPException(status_code=400, detail=f"{file.filename}は既に処理済みです")
    
    content = await file.read()
    texts_count = await process_pdf_content(content, file.filename)
    
    processed_files.add(file.filename)
    save_processed_files(processed_files)
    
    return {"message": f"{file.filename}を処理しました", "texts_count": texts_count}

@app.post("/reindex")
async def reindex():
    """既存のインデックスを再構築する"""
    if not processed_files:
        raise HTTPException(status_code=404, detail="処理済みのファイルが見つかりません")
    
    try:
        # インデックスの初期化
        indexer.index = faiss.IndexFlatIP(indexer.dimension)
        indexer.metadata = []
        
        # ファイル管理の初期化
        processed_files.clear()
        save_processed_files(processed_files)
        
        # 各ファイルの再処理
        total_processed = 0
        for file_path in list(processed_files):
            path = Path(file_path)
            if path.exists():
                content = path.read_bytes()
                await process_pdf_content(content, file_path)
                processed_files.add(file_path)
                total_processed += 1
        
        save_processed_files(processed_files)
        return {"message": f"{total_processed}個のファイルを再インデックスしました"}
        
    except Exception as e:
        logger.error(f"再インデックス中にエラー発生: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search", response_model=SearchResponse)
async def search(query: str, top_k: Optional[int] = 3):
    """テキストによる検索を実行する"""
    try:
        logger.info(f"検索クエリを処理: {query}")
        
        query_vector = embedder.generate_embedding(query)
        results = indexer.search(query_vector, top_k)
        
        search_results = [
            SearchResult(
                text=metadata["text"],
                score=float(score),
                file=metadata["file"],
                page=metadata["page"]
            )
            for metadata, score in results
        ]
        
        return SearchResponse(results=search_results)
        
    except Exception as e:
        logger.error(f"検索中にエラー発生: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 