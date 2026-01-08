"""ベクトルインデックス - FAISSによる高速類似検索"""

from typing import List, Dict, Tuple
import numpy as np
import faiss
import os
from pathlib import Path
import logging

from .database import Database

logger = logging.getLogger(__name__)


class Indexer:
    """FAISSベクトルインデックス

    IVF-PQ (IVF256,PQ16,RFlat) を使用:
    - IVF256: 256クラスタで粗い検索を高速化
    - PQ16: 16サブベクトルに分割して圧縮
    - RFlat: 正確な距離で再ランキング
    """

    def __init__(self, dimension: int = 512, index_key: str = "IVF256,PQ16,RFlat"):
        self.dimension = dimension
        self.index_key = index_key
        self.min_training_size = 39 * 256  # IVF256の訓練に必要な最小データ数

        # 初期状態は一時インデックス（訓練データが貯まるまで）
        self._init_temp_index()

        # メタデータはSQLiteで管理
        self.db = Database()

    def _init_temp_index(self) -> None:
        """一時インデックスの初期化（少量データ用）"""
        self.temp_index = faiss.IndexFlatIP(self.dimension)
        self.index = None
        self.is_trained = False

    def _init_ivf_pq(self, vectors: np.ndarray) -> None:
        """IVF-PQインデックスの初期化と訓練"""
        logger.info(f"IVF-PQインデックスの訓練を開始（データ数: {len(vectors)}）")

        self.index = faiss.index_factory(self.dimension, self.index_key, faiss.METRIC_INNER_PRODUCT)

        if hasattr(self.index, 'k_factor_rf'):
            self.index.k_factor_rf = 10

        self.index.train(vectors)
        self.index.add(vectors)
        self.is_trained = True
        self.temp_index = None

        logger.info("IVF-PQインデックスの訓練が完了")

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """L2正規化（コサイン類似度のため）"""
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, np.finfo(vectors.dtype).tiny)
        return vectors / norms

    def add(self, vectors: np.ndarray, metadata: List[Dict]) -> None:
        """ベクトルとメタデータを追加

        重要: ベクトルを先に追加し、成功後にメタデータを追加。
        これにより、途中クラッシュ時のデータ不整合を防ぐ。
        """
        if len(vectors) == 0:
            return

        if isinstance(vectors, list):
            vectors = np.array(vectors, dtype=np.float32)

        normalized = self._normalize(vectors.copy())

        # 1. ベクトルを先に追加
        if self.is_trained:
            self.index.add(normalized)
        else:
            self.temp_index.add(normalized)

        # 2. ベクトル追加成功後にメタデータを追加
        start_id = self.db.get_metadata_count()
        self.db.add_metadata(metadata, start_id)

        # 3. 訓練閾値に達したらIVF-PQに移行
        if not self.is_trained and self.temp_index.ntotal >= self.min_training_size:
            all_vectors = np.empty((self.temp_index.ntotal, self.dimension), dtype=np.float32)
            self.temp_index.reconstruct_n(0, self.temp_index.ntotal, all_vectors)
            self._init_ivf_pq(all_vectors)

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """ベクトル検索"""
        active = self.index if self.is_trained else self.temp_index

        if active is None or active.ntotal == 0:
            return []

        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        normalized = self._normalize(query_vector.copy())

        if self.is_trained:
            self.index.nprobe = 10

        scores, indices = active.search(normalized, top_k)
        indices = indices[0]
        scores = scores[0]

        metadata_list = self.db.get_metadata([int(i) for i in indices if i >= 0])
        return [(m, float(s)) for m, s in zip(metadata_list, scores) if m]

    def get_vector_count(self) -> int:
        """ベクトル数を取得"""
        if self.is_trained and self.index:
            return self.index.ntotal
        if self.temp_index:
            return self.temp_index.ntotal
        return 0

    def save(self, index_dir: str = "embeddings") -> None:
        """インデックスを保存（FAISSバイナリ + メタデータ）"""
        index_dir = Path(index_dir)
        index_dir.mkdir(exist_ok=True)

        # FAISSインデックスをバイナリ保存（訓練済み状態を維持）
        faiss_path = index_dir / "faiss.index"
        active = self.index if self.is_trained else self.temp_index

        if active and active.ntotal > 0:
            faiss.write_index(active, str(faiss_path))

        # 訓練状態を保存
        state_path = index_dir / "index_state.json"
        import json
        state_path.write_text(json.dumps({
            "is_trained": self.is_trained,
            "dimension": self.dimension,
            "index_key": self.index_key,
            "vector_count": self.get_vector_count(),
        }))

        # メタデータをフラッシュ
        self.db.flush()

        faiss_size = os.path.getsize(faiss_path) / (1024 * 1024) if faiss_path.exists() else 0
        db_size = os.path.getsize(self.db.db_path) / (1024 * 1024)
        logger.info(f"保存: ベクトル{self.get_vector_count()}件 (FAISS {faiss_size:.1f}MB), DB ({db_size:.1f}MB)")

    def load(self, index_dir: str = "embeddings") -> None:
        """インデックスを読み込み（FAISSバイナリから高速ロード）"""
        import json
        index_dir = Path(index_dir)
        faiss_path = index_dir / "faiss.index"
        state_path = index_dir / "index_state.json"
        vector_path = index_dir / "vectors.npz"  # 旧形式との互換性

        # 新形式: FAISSバイナリから読み込み（高速）
        if faiss_path.exists() and state_path.exists():
            state = json.loads(state_path.read_text())
            self.is_trained = state.get("is_trained", False)

            loaded_index = faiss.read_index(str(faiss_path))

            if self.is_trained:
                self.index = loaded_index
                self.temp_index = None
            else:
                self.temp_index = loaded_index
                self.index = None

            logger.info(f"読み込み: ベクトル{self.get_vector_count()}件, メタデータ{self.db.get_metadata_count()}件")
            return

        # 旧形式: vectors.npzから読み込み（互換性維持、初回のみ訓練）
        if vector_path.exists():
            logger.info("旧形式(vectors.npz)から読み込み中...")
            with np.load(vector_path) as data:
                vectors = data['vectors']
                if len(vectors) >= self.min_training_size:
                    self._init_ivf_pq(vectors)
                else:
                    self._init_temp_index()
                    if len(vectors) > 0:
                        self.temp_index.add(vectors)

            logger.info(f"読み込み: ベクトル{self.get_vector_count()}件, メタデータ{self.db.get_metadata_count()}件")
            # 新形式に変換して保存
            logger.info("新形式(faiss.index)に変換して保存...")
            self.save(str(index_dir))
            return

        logger.warning("インデックスファイルが見つかりません")
        self._init_temp_index()

    def verify_integrity(self) -> Tuple[bool, str]:
        """データ整合性を検証"""
        vector_count = self.get_vector_count()
        metadata_count = self.db.get_metadata_count()

        if vector_count != metadata_count:
            return False, f"不整合: ベクトル{vector_count}件 != メタデータ{metadata_count}件"
        return True, f"整合: {vector_count}件"
