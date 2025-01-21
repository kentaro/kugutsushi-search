from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import logging

from src.embedder import Embedder
from src.indexer import Indexer
from src.extractor import extract_from_pdf

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kugutsushi Search API",
    description="PDF文書の検索APIサーバー",
    version="0.1.0"
)

embedder = Embedder()
indexer = Indexer()

# 処理済みファイルを管理
PROCESSED_FILES_PATH = "embeddings/processed_files.json"
os.makedirs("embeddings", exist_ok=True)

def load_processed_files():
    if os.path.exists(PROCESSED_FILES_PATH):
        with open(PROCESSED_FILES_PATH, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_processed_files(files):
    with open(PROCESSED_FILES_PATH, 'w', encoding='utf-8') as f:
        json.dump(list(files), f, ensure_ascii=False, indent=2)

processed_files = load_processed_files()

class SearchResult(BaseModel):
    text: str
    score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDFファイルのみアップロード可能です")
    
    try:
        logger.info(f"PDFファイルを処理開始: {file.filename}")
        
        # 既に処理済みのファイルはスキップ
        if file.filename in processed_files:
            logger.info(f"ファイルはすでに処理済み: {file.filename}")
            return {"message": f"{file.filename}は既に処理済みです", "texts_count": 0, "skipped": True}
        
        # PDFからテキストを抽出
        content = await file.read()
        logger.info(f"PDFファイルを読み込み: {len(content)} bytes")
        
        texts = extract_from_pdf(content)
        logger.info(f"テキスト抽出完了: {len(texts)}件")
        
        # テキストをベクトル化してインデックスに追加
        vectors = embedder.generate_embeddings(texts)
        logger.info(f"ベクトル生成完了: {len(vectors)}件")
        
        indexer.add(vectors, texts)
        logger.info("インデックスに追加完了")
        
        # インデックスを保存
        indexer.save()
        logger.info("インデックスを保存完了")
        
        # 処理済みファイルとして記録
        processed_files.add(file.filename)
        save_processed_files(processed_files)
        logger.info("処理済みファイルを記録完了")
        
        return {"message": f"{file.filename}を正常に処理しました", "texts_count": len(texts), "skipped": False}
    except Exception as e:
        logger.error(f"エラーが発生: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search", response_model=SearchResponse)
async def search(query: str, top_k: Optional[int] = 3):
    try:
        logger.info(f"検索クエリを処理: {query}")
        
        # クエリをベクトル化
        query_vector = embedder.generate_embedding(query)
        logger.info("クエリのベクトル化完了")
        
        # 検索を実行
        results = indexer.search(query_vector, top_k)
        logger.info(f"検索完了: {len(results)}件")
        
        # レスポンスを整形
        search_results = [
            SearchResult(text=metadata["text"], score=float(score))
            for metadata, score in results
        ]
        
        return SearchResponse(results=search_results)
    except Exception as e:
        logger.error(f"エラーが発生: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 