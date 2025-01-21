from typing import List, Dict, Tuple
import numpy as np
import faiss
import json
import os
from pathlib import Path

class Indexer:
    def __init__(self, dimension: int = 1024, index_dir: str = "embeddings", index_name: str = "default"):
        """
        Args:
            dimension: ベクトルの次元数（static-embedding-japaneseは1024次元）
            index_dir: インデックスファイルを保存するディレクトリ
            index_name: インデックスファイルの名前
        """
        self.dimension = dimension
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(exist_ok=True)
        self.index_name = index_name
        
        # インデックスファイルが存在する場合は読み込む
        index_path = self.index_dir / f"{self.index_name}.faiss"
        metadata_path = self.index_dir / f"{self.index_name}.json"
        
        if index_path.exists() and metadata_path.exists():
            self.load(self.index_name)
        else:
            # L2正規化済みのベクトル用にInnerProductを使用
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata: List[Dict] = []

    def add(self, vectors: np.ndarray, metadata_list: List[Dict]) -> None:
        """ベクトルとメタデータをインデックスに追加"""
        if len(vectors) != len(metadata_list):
            raise ValueError("vectors and metadata_list must have the same length")
        
        self.index.add(vectors)
        self.metadata.extend(metadata_list)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """
        クエリベクトルに最も近い文書を検索
        
        Args:
            query_vector: 検索クエリのベクトル
            top_k: 返す結果の数
            
        Returns:
            [(メタデータ, スコア), ...]のリスト
        """
        # query_vectorが2次元でない場合は2次元に変換
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        # 検索実行
        scores, indices = self.index.search(query_vector, top_k)
        
        # 結果を整形
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1:  # -1は無効なインデックス
                results.append((self.metadata[idx], float(score)))
        
        return results

    def save(self, index_name: str = None) -> None:
        """インデックスとメタデータを保存"""
        if index_name is None:
            index_name = self.index_name
            
        # インデックスの保存
        index_path = self.index_dir / f"{index_name}.faiss"
        faiss.write_index(self.index, str(index_path))
        
        # メタデータの保存
        metadata_path = self.index_dir / f"{index_name}.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def load(self, index_name: str = None) -> None:
        """インデックスとメタデータを読み込み"""
        if index_name is None:
            index_name = self.index_name
            
        # インデックスの読み込み
        index_path = self.index_dir / f"{index_name}.faiss"
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")
        self.index = faiss.read_index(str(index_path))
        
        # メタデータの読み込み
        metadata_path = self.index_dir / f"{index_name}.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f) 