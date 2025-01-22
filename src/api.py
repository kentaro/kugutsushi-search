from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import logging
from pathlib import Path

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

def process_pdf(file_path: str, force: bool = False) -> None:
    processed_files = load_processed_files()
    
    if not force and str(file_path) in processed_files:
        return
    
    # PDFからテキストを抽出
    texts = extract_from_pdf(file_path)
    
    # ベクトルを生成
    vectors = []
    metadata = []
    for page, text in enumerate(texts):
        vector = embedder.generate_embedding(text)
        vectors.append(vector)
        metadata.append({
            "text": text,
            "file": str(file_path),
            "page": page
        })
    
    # インデックスに追加
    indexer.add(vectors, metadata)
    indexer.save()
    
    # 処理済みファイルを記録
    if not force:
        processed_files.add(str(file_path))
        save_processed_files(processed_files)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDFファイルのみアップロード可能です")
    
    # 一時ファイルとして保存
    temp_file = Path("embeddings") / file.filename
    try:
        with open(temp_file, "wb") as f:
            f.write(await file.read())
        
        # PDFを処理
        process_pdf(temp_file)
        
        return {"message": f"{file.filename}を処理しました"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 一時ファイルを削除
        if temp_file.exists():
            temp_file.unlink()

@app.post("/reindex")
async def reindex():
    """既存のインデックスを再構築します。"""
    try:
        # 処理済みファイルのリストを取得
        processed_files = load_processed_files()
        if not processed_files:
            raise HTTPException(status_code=404, detail="処理済みのファイルが見つかりません")
        
        # インデックスを初期化
        indexer.index = faiss.IndexFlatIP(indexer.dimension)
        indexer.metadata = []
        
        # 各ファイルを再処理
        for file_path in processed_files:
            if Path(file_path).exists():
                process_pdf(file_path, force=True)
            
        return {"message": f"{len(processed_files)}個のファイルを再インデックスしました"}
    except Exception as e:
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