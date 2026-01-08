"""BM25インデクサーのテスト"""

import pytest
import shutil
from pathlib import Path

from src.bm25_indexer import BM25Indexer


@pytest.fixture
def test_dir(tmp_path):
    """テスト用一時ディレクトリ"""
    yield tmp_path
    if tmp_path.exists():
        shutil.rmtree(tmp_path)


class TestBM25Indexer:
    def test_add_and_search(self, test_dir):
        """追加と検索"""
        bm25 = BM25Indexer(db_path=str(test_dir / "bm25.db"), min_df=1)

        texts = [
            "美味しいラーメン屋に行きたい",
            "素敵なカフェが近所にあるよ",
            "新鮮な魚介を提供する店です",
            "隠れた豚骨の名店だよ",
            "おすすめの中華そばの店",
        ]
        bm25.add(texts)

        assert bm25.corpus_size == 5
        assert bm25.vocab_size > 0

        results = bm25.search("ラーメン", top_k=3)
        assert len(results) > 0
        # ラーメン関連の文書が上位に来るはず
        top_doc_id = results[0][0]
        assert top_doc_id in [0, 3, 4]  # ラーメン、豚骨、中華そば

    def test_tokenize(self, test_dir):
        """トークナイズ（単語+2gram）"""
        bm25 = BM25Indexer(db_path=str(test_dir / "bm25.db"))

        tokens = bm25.tokenize("日本語テスト")
        # 単語全体 + 2gramが生成される
        assert "日本語テスト" in tokens  # 単語全体
        assert "日本" in tokens  # 2gram
        assert "本語" in tokens  # 2gram

    def test_save_and_load(self, test_dir):
        """保存と読み込み"""
        bm25 = BM25Indexer(db_path=str(test_dir / "bm25.db"), min_df=1)
        bm25.add(["テスト文書1", "テスト文書2"])
        bm25.save(str(test_dir))

        new_bm25 = BM25Indexer(db_path=str(test_dir / "bm25.db"), min_df=1)
        new_bm25.load(str(test_dir))

        assert new_bm25.corpus_size == 2

    def test_empty_search(self, test_dir):
        """空のインデックスでの検索"""
        bm25 = BM25Indexer(db_path=str(test_dir / "bm25.db"))
        results = bm25.search("テスト", top_k=10)
        assert len(results) == 0

    def test_prune_vocabulary(self, test_dir):
        """語彙削減"""
        bm25 = BM25Indexer(db_path=str(test_dir / "bm25.db"), min_df=1)

        texts = [
            "共通の単語がある",
            "共通の単語がある",
            "レアな単語xyz",
        ]
        bm25.add(texts)

        original_vocab = bm25.vocab_size
        deleted = bm25.prune_vocabulary(min_df=2)

        assert deleted > 0
        assert bm25.vocab_size < original_vocab
