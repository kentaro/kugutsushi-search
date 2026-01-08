"""Extractorのテスト"""

import pytest

from src.extractor import chunk_text
from src.text_filter import is_content_page


class TestChunkText:
    def test_short_text(self):
        """短いテキストはそのまま1チャンク"""
        text = "これは短いテキストです。"
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_split(self):
        """長いテキストは分割される"""
        text = "あ" * 1000
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) >= 2

    def test_sentence_boundary(self):
        """文境界で分割される"""
        text = "これは最初の文です。これは二番目の文です。これは三番目の文です。" * 50
        chunks = chunk_text(text, chunk_size=100)
        # 各チャンクは文の途中で切れない
        for chunk in chunks:
            assert chunk.endswith("。") or len(chunk) < 100


class TestTextFilter:
    def test_content_page(self):
        """コンテンツページは通過"""
        # MIN_UNIQUE_CHARS=20を満たす多様な文字を含むテキスト
        text = "これは本文です。様々な内容を含む長い文章で、色々な漢字やひらがなカタカナが混在しています。" * 5
        assert is_content_page(text) is True

    def test_short_page_filtered(self):
        """短いページはフィルタ"""
        text = "目次"
        assert is_content_page(text) is False

    def test_toc_page_filtered(self):
        """目次ページはフィルタ"""
        text = "目次\n" + "あ" * 50
        assert is_content_page(text) is False

    def test_numbers_only_filtered(self):
        """数字のみのページはフィルタ"""
        text = "123 456 789 " * 20
        assert is_content_page(text) is False
