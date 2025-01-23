from typing import List, Dict, Tuple
import numpy as np
import faiss
import json
import os
from pathlib import Path
import logging
import numpy.lib.format as npy_format

logger = logging.getLogger(__name__)

class Indexer:
    def __init__(self, dimension: int = 1024):  # static-embedding-japaneseは1024次元
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)  # 内積で類似度を計算
        self.metadata = []
    
    def normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """ベクトルをL2正規化する"""
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        # L2ノルムを計算（各行ベクトルのノルム）
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # ゼロ除算を防ぐ
        norms = np.maximum(norms, np.finfo(vectors.dtype).tiny)
        # 正規化
        return vectors / norms
    
    def add(self, vectors: np.ndarray, metadata: list) -> None:
        if len(vectors) == 0:
            return
        
        if isinstance(vectors, list):
            vectors = np.array(vectors, dtype=np.float32)
        
        # L2正規化を適用
        normalized_vectors = self.normalize_vectors(vectors.copy())  # 元の配列を変更しないようにコピー
        self.index.add(normalized_vectors)
        self.metadata.extend(metadata)
    
    def search(self, query_vector: np.ndarray, top_k: int = 3) -> list:
        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)
        elif len(query_vector.shape) == 1:
            query_vector = query_vector.reshape(1, -1)
        
        # クエリベクトルもL2正規化
        normalized_query = self.normalize_vectors(query_vector.copy())
        scores, indices = self.index.search(normalized_query, top_k)
        return [(self.metadata[idx], score) for idx, score in zip(indices[0], scores[0])]

    def save(self, index_dir: str = "embeddings") -> None:
        """インデックスをプラットフォーム非依存な形式で保存（圧縮あり）"""
        index_dir = Path(index_dir)
        index_dir.mkdir(exist_ok=True)
        
        # メタデータを保存
        metadata_path = index_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        
        # インデックスの生ベクトルを取得（すでに正規化済み）
        vector_path = index_dir / "vectors.npz"
        if self.index.ntotal > 0:  # インデックスが空でない場合のみベクトルを取得
            # numpy配列を直接取得
            vectors = np.empty((self.index.ntotal, self.dimension), dtype=np.float32)
            self.index.reconstruct_n(0, self.index.ntotal, vectors)
            # ベクトルを圧縮して保存
            np.savez_compressed(vector_path, vectors=vectors)
        else:
            # 空のインデックスの場合は空の配列を保存
            empty_vectors = np.array([], dtype=np.float32).reshape(0, self.dimension)
            np.savez_compressed(vector_path, vectors=empty_vectors)
        
        # サイズ情報をログ出力
        vector_size = os.path.getsize(vector_path) / (1024 * 1024)  # MB単位
        metadata_size = os.path.getsize(metadata_path) / (1024 * 1024)  # MB単位
        logger.info(f"インデックスを保存: {len(self.metadata)}件")
        logger.info(f"ベクトルファイルサイズ: {vector_size:.2f}MB")
        logger.info(f"メタデータファイルサイズ: {metadata_size:.2f}MB")
        logger.debug(f"メタデータ: {metadata_path}")
        logger.debug(f"ベクトル: {vector_path}")
    
    def load(self, index_dir: str = "embeddings") -> None:
        """圧縮されたインデックスを読み込み"""
        index_dir = Path(index_dir)
        metadata_path = index_dir / "metadata.json"
        vector_path = index_dir / "vectors.npz"
        
        if not metadata_path.exists() or not vector_path.exists():
            logger.warning("インデックスファイルが見つかりません")
            return
        
        # メタデータを読み込み
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
        
        # 圧縮されたベクトルを読み込んでインデックスを再構築
        with np.load(vector_path) as data:
            vectors = data['vectors']
            self.index = faiss.IndexFlatIP(self.dimension)
            if len(vectors) > 0:
                # ベクトルはすでに正規化済みなので、そのまま追加
                self.index.add(vectors)
        
        # サイズ情報をログ出力
        vector_size = os.path.getsize(vector_path) / (1024 * 1024)  # MB単位
        metadata_size = os.path.getsize(metadata_path) / (1024 * 1024)  # MB単位
        logger.info(f"インデックスを読み込み: {len(self.metadata)}件")
        logger.info(f"ベクトルファイルサイズ: {vector_size:.2f}MB")
        logger.info(f"メタデータファイルサイズ: {metadata_size:.2f}MB")
        logger.debug(f"ベクトルの形状: {vectors.shape}") 