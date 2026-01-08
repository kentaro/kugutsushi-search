"""リランカー - Cross-Encoderによる再ランキング"""

from typing import List, Tuple, Dict, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)

RERANKER_MODEL = "hotchpotch/japanese-reranker-tiny-v2"


class Reranker:
    """日本語Cross-Encoderリランカー

    hotchpotch/japanese-reranker-tiny-v2:
    - 3レイヤー, 256隠れ層
    - Raspberry Pi 4Bで約15-25ms/ペア
    """

    def __init__(self, model_name: str = RERANKER_MODEL):
        self.model_name = model_name
        self.model = None

    def _load_model(self) -> None:
        """モデルを遅延ロード"""
        if self.model is not None:
            return

        logger.info(f"リランカーをロード: {self.model_name}")
        start = time.time()

        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(self.model_name, max_length=512, device="cpu")

        logger.info(f"リランカーロード完了: {time.time() - start:.2f}秒")

    def rerank(
        self,
        query: str,
        results: List[Tuple[Dict[str, Any], float]],
        top_k: Optional[int] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """検索結果をリランキング"""
        if not results:
            return []

        self._load_model()

        pairs = [(query, r[0]["text"]) for r in results]

        start = time.time()
        scores = self.model.predict(pairs)
        elapsed = time.time() - start

        logger.debug(f"リランキング: {len(pairs)}件, {elapsed:.3f}秒")

        reranked = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)

        if top_k:
            reranked = reranked[:top_k]

        return [(item[0], float(score)) for item, score in reranked]


_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    """シングルトン取得"""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
