"""Embedderのテスト"""

import pytest
import numpy as np

from src.embedder import Embedder


@pytest.fixture(scope="module")
def embedder():
    """Embedderインスタンス（モジュールスコープで共有）"""
    return Embedder()


class TestEmbedder:
    def test_generate_query_embedding(self, embedder):
        """クエリベクトル生成"""
        vector = embedder.generate_query_embedding("ラーメンが食べたい")

        assert isinstance(vector, np.ndarray)
        assert vector.shape == (512,)
        assert not np.isnan(vector).any()

    def test_generate_document_embedding(self, embedder):
        """ドキュメントベクトル生成"""
        vector = embedder.generate_document_embedding("美味しいラーメン屋です")

        assert isinstance(vector, np.ndarray)
        assert vector.shape == (512,)

    def test_generate_document_embeddings_batch(self, embedder):
        """バッチベクトル生成"""
        texts = [
            "これは日本語のテストテキストです。",
            "文ベクトルの生成をテストします。",
            "複数の文章を一度に処理できます。",
        ]
        vectors = embedder.generate_document_embeddings(texts)

        assert isinstance(vectors, np.ndarray)
        assert vectors.shape == (3, 512)

    def test_dimension(self, embedder):
        """次元数"""
        assert embedder.dimension == 512
