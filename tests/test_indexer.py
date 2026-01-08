"""インデクサーのテスト"""

import pytest
import shutil
import numpy as np
from pathlib import Path

from src.indexer import Indexer
from src.embedder import Embedder


@pytest.fixture
def test_dir(tmp_path):
    """テスト用一時ディレクトリ"""
    yield tmp_path
    if tmp_path.exists():
        shutil.rmtree(tmp_path)


@pytest.fixture
def embedder():
    """Embedderインスタンス"""
    return Embedder()


@pytest.fixture
def sample_data(embedder):
    """テストデータ"""
    texts = [
        "美味しいラーメン屋に行きたい",
        "素敵なカフェが近所にあるよ。落ち着いた雰囲気。",
        "新鮮な魚介を提供する店です。",
        "隠れた豚骨の名店だよ。スープが最高。",
        "おすすめの中華そばの店を教えてあげる。",
    ]
    metadata = [{"text": t, "file": "test.pdf", "page": i} for i, t in enumerate(texts)]
    vectors = embedder.generate_document_embeddings(texts)
    return texts, metadata, vectors


class TestIndexer:
    def test_add_and_search(self, test_dir, embedder, sample_data):
        """ベクトル追加と検索"""
        texts, metadata, vectors = sample_data

        # テスト用のパスでDatabaseを再初期化
        from src.database import Database
        indexer = Indexer()
        indexer.db = Database(db_path=str(test_dir / "metadata.db"))
        indexer.add(vectors, metadata)
        indexer.db.flush()  # バッファをDBに書き込み

        assert indexer.get_vector_count() == len(texts)

        query_vec = embedder.generate_query_embedding("ラーメンが食べたい")
        results = indexer.search(query_vec, top_k=3)

        assert len(results) == 3
        # ラーメン関連のテキストが上位に来るはず
        top_text = results[0][0]["text"]
        assert "ラーメン" in top_text or "豚骨" in top_text or "中華そば" in top_text

    def test_save_and_load(self, test_dir, embedder, sample_data):
        """保存と読み込み"""
        texts, metadata, vectors = sample_data

        from src.database import Database
        indexer = Indexer()
        indexer.db = Database(db_path=str(test_dir / "metadata.db"))
        indexer.add(vectors, metadata)
        indexer.save(str(test_dir))

        new_indexer = Indexer()
        new_indexer.db = Database(db_path=str(test_dir / "metadata.db"))
        new_indexer.load(str(test_dir))

        assert new_indexer.get_vector_count() == len(texts)

    def test_verify_integrity(self, test_dir, sample_data):
        """整合性チェック"""
        texts, metadata, vectors = sample_data

        from src.database import Database
        indexer = Indexer()
        indexer.db = Database(db_path=str(test_dir / "metadata.db"))
        indexer.add(vectors, metadata)

        ok, msg = indexer.verify_integrity()
        assert ok is True
        assert "整合" in msg

    def test_empty_search(self, test_dir):
        """空のインデックスでの検索"""
        from src.database import Database
        indexer = Indexer()
        indexer.db = Database(db_path=str(test_dir / "metadata.db"))

        query_vec = np.random.randn(512).astype(np.float32)
        results = indexer.search(query_vec, top_k=10)

        assert len(results) == 0
