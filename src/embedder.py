"""埋め込み生成 - Ruri v3による日本語テキストのベクトル化"""

from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer

# Ruri v3のプレフィックス（公式推奨）
QUERY_PREFIX = "検索クエリ: "
DOCUMENT_PREFIX = "検索文書: "


class Embedder:
    """Ruri v3-130mによる埋め込み生成器

    512次元のベクトルを生成。クエリとドキュメントで異なるプレフィックスを使用。
    """

    def __init__(self, device: str = "cpu"):
        self.model = SentenceTransformer("cl-nagoya/ruri-v3-130m", device=device)
        self.dimension = 512

    def generate_query_embedding(self, query: str) -> np.ndarray:
        """検索クエリをベクトル化"""
        return self.model.encode(QUERY_PREFIX + query)

    def generate_document_embedding(self, text: str) -> np.ndarray:
        """単一ドキュメントをベクトル化"""
        return self.model.encode(DOCUMENT_PREFIX + text)

    def generate_document_embeddings(self, texts: List[str]) -> np.ndarray:
        """複数ドキュメントを一括ベクトル化（効率的）"""
        prefixed = [DOCUMENT_PREFIX + t for t in texts]
        return self.model.encode(prefixed)

    # 以下はbatch_index.pyとの互換性のためのエイリアス
    def generate_embedding(self, text: str) -> np.ndarray:
        """テキストをベクトル化（ドキュメントとして扱う）"""
        return self.generate_document_embedding(text)

    def generate_embeddings(self, texts: List[Dict]) -> np.ndarray:
        """複数テキストを一括ベクトル化（Dict形式入力）"""
        text_list = [t["text"] for t in texts]
        return self.generate_document_embeddings(text_list)
