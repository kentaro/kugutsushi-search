"""ハイブリッド検索 - ベクトル + BM25 + リランキング"""

from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
import logging
import math

from .embedder import Embedder
from .indexer import Indexer
from .bm25_indexer import BM25Indexer
from .reranker import get_reranker

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """検索設定"""
    use_bm25: bool = True
    use_rerank: bool = True
    retrieval_k: int = 100  # RRF候補数（増やしても速度影響小）
    rerank_top_k: int = 20  # rerank対象数（速度に直結）
    rerank_weight: float = 0.5  # reranker:RRF = 50:50でブレンド


class HybridSearcher:
    """ハイブリッド検索エンジン

    1. ベクトル検索（意味的類似度）
    2. BM25検索（キーワードマッチ）
    3. RRF（Reciprocal Rank Fusion）でスコア融合
    4. Cross-Encoderでリランキング
    """

    def __init__(self, embedder: Embedder, indexer: Indexer, bm25: BM25Indexer):
        self.embedder = embedder
        self.indexer = indexer
        self.bm25 = bm25

    def search(
        self,
        query: str,
        top_k: int = 10,
        config: Optional[SearchConfig] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """ハイブリッド検索"""
        if config is None:
            config = SearchConfig()

        # 1. ベクトル検索
        query_vec = self.embedder.generate_query_embedding(query)
        vector_results = self.indexer.search(query_vec, config.retrieval_k)

        if not config.use_bm25:
            candidates = vector_results
        else:
            # 2. BM25検索
            bm25_results = self.bm25.search(query, config.retrieval_k)
            # 3. RRFで融合
            candidates = self._rrf(vector_results, bm25_results)

        # 4. リランキング（RRFスコアとブレンド）
        if config.use_rerank and candidates:
            candidates = candidates[:config.rerank_top_k]
            reranker = get_reranker()
            reranked = reranker.rerank(query, candidates)

            # RRFスコアを正規化（0-1）- file+pageをキーに
            def doc_key(m):
                return (m.get("file", ""), m.get("page", 0))

            rrf_scores = {doc_key(c[0]): c[1] for c in candidates}
            max_rrf = max(rrf_scores.values()) if rrf_scores else 1.0

            # rerankerスコアとRRFスコアをブレンド
            blended = []
            for metadata, rerank_score in reranked:
                rrf_norm = rrf_scores.get(doc_key(metadata), 0) / max_rrf
                # rerankerスコアを0-1にシグモイド正規化
                rerank_norm = 1 / (1 + math.exp(-rerank_score))
                final_score = (
                    config.rerank_weight * rerank_norm +
                    (1 - config.rerank_weight) * rrf_norm
                )
                blended.append((metadata, final_score))

            blended.sort(key=lambda x: x[1], reverse=True)
            return blended[:top_k]

        return candidates[:top_k]

    def _rrf(
        self,
        vector_results: List[Tuple[Dict, float]],
        bm25_results: List[Tuple[int, float]],
        k: int = 60
    ) -> List[Tuple[Dict, float]]:
        """Reciprocal Rank Fusion

        RRF(d) = Σ 1 / (k + rank(d))
        """
        rrf_scores: Dict[int, float] = {}
        doc_metadata: Dict[int, Dict] = {}

        # ベクトル検索結果
        for rank, (metadata, _) in enumerate(vector_results):
            doc_key = hash((metadata.get("file", ""), metadata.get("page", 0)))
            rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (k + rank + 1)
            doc_metadata[doc_key] = metadata

        # BM25結果（バッチ取得）
        bm25_indices = [idx for idx, _ in bm25_results]
        bm25_metadata_list = self.indexer.db.get_metadata(bm25_indices)

        for rank, metadata in enumerate(bm25_metadata_list):
            if not metadata:
                continue
            doc_key = hash((metadata.get("file", ""), metadata.get("page", 0)))
            rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + 1.0 / (k + rank + 1)
            if doc_key not in doc_metadata:
                doc_metadata[doc_key] = metadata

        # スコア順にソート
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_metadata[doc_key], s) for doc_key, s in sorted_docs]
