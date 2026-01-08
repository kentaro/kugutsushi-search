"""インデックス作成 - PDF処理からインデックス追加までの共通ライブラリ"""

from typing import List, Dict, Tuple
from pathlib import Path
import numpy as np
import logging
import gc

from .embedder import Embedder
from .indexer import Indexer
from .extractor import extract_from_pdf, chunk_text
from .text_filter import is_content_page
from .bm25_indexer import BM25Indexer

logger = logging.getLogger(__name__)

BATCH_SIZE = 32


class IndexBuilder:
    """インデックス構築器

    batch_index.py と api.py で共有。
    """

    def __init__(
        self,
        embedder: Embedder = None,
        indexer: Indexer = None,
        bm25: BM25Indexer = None
    ):
        self.embedder = embedder or Embedder()
        self.indexer = indexer or Indexer()
        self.bm25 = bm25 or BM25Indexer()

    def load(self) -> None:
        """既存インデックスを読み込み"""
        self.indexer.load()
        self.bm25.load()

    def save(self) -> None:
        """インデックスを保存"""
        self.indexer.save()
        self.bm25.save()

    def add_pdf(self, pdf_data: bytes, filename: str) -> Tuple[int, str]:
        """PDFをインデックスに追加

        Args:
            pdf_data: PDFのバイナリデータ
            filename: ファイル名

        Returns:
            (追加チャンク数, メッセージ)
        """
        try:
            # テキスト抽出
            pages = extract_from_pdf(pdf_data)
            pages = [p for p in pages if is_content_page(p["text"])]

            if not pages:
                return 0, "テキストなし"

            # チャンキング: 各ページを500文字程度に分割
            metadata = []
            for p in pages:
                chunks = chunk_text(p["text"].strip())
                for i, chunk in enumerate(chunks):
                    metadata.append({
                        "text": chunk,
                        "file": filename,
                        "page": p["page"] - 1,
                        "chunk": i,
                    })

            if not metadata:
                return 0, "チャンクなし"

            # ベクトル生成（バッチ処理）
            text_list = [m["text"] for m in metadata]
            vectors = self._generate_vectors_batch(text_list)

            # インデックスに追加
            self.indexer.add(vectors, metadata)
            self.bm25.add(text_list)

            return len(metadata), "OK"

        except Exception as e:
            logger.error(f"PDF処理エラー: {e}")
            return 0, str(e)
        finally:
            gc.collect()

    def add_pdf_file(self, path: Path) -> Tuple[int, str]:
        """PDFファイルをインデックスに追加"""
        content = path.read_bytes()
        result = self.add_pdf(content, path.name)
        del content
        gc.collect()
        return result

    def _generate_vectors_batch(self, texts: List[str]) -> np.ndarray:
        """バッチでベクトル生成"""
        vectors = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            batch_vecs = self.embedder.generate_document_embeddings(batch)
            vectors.extend(batch_vecs)
        return np.array(vectors, dtype=np.float32)

    def verify(self) -> Tuple[bool, str]:
        """整合性チェック"""
        return self.indexer.verify_integrity()

    @property
    def stats(self) -> Dict:
        """統計情報"""
        return {
            "vectors": self.indexer.get_vector_count(),
            "metadata": self.indexer.db.get_metadata_count(),
            "bm25": self.bm25.corpus_size,
        }
