from typing import List, Dict, Tuple
import numpy as np
import faiss
import os
from pathlib import Path
import logging
import numpy.lib.format as npy_format
from .database import Database

logger = logging.getLogger(__name__)

class Indexer:
    def __init__(self, dimension: int = 128):  # truncate_dimで128次元に削減
        self.dimension = dimension
        # IVF-PQの設定
        self.nlist = 100  # クラスタ数（データ量に応じて調整）
        self.m = 16  # サブベクトルの数（dimension を 8 で割り切れる数）
        self.nbits = 8  # 各サブベクトルのビット数
        
        # 訓練に必要なデータ数（nlist * 39）
        self.min_training_size = self.nlist * 39
        
        # 初期状態では一時インデックスを使用
        self._init_temp_index()
        
        # メタデータをSQLiteで管理
        self.db = Database()
    
    def _init_temp_index(self):
        """一時インデックスの初期化"""
        self.temp_index = faiss.IndexFlatIP(self.dimension)
        self.index = None
        self.is_trained = False
    
    def _init_ivf_pq(self, vectors: np.ndarray):
        """IVF-PQインデックスの初期化と訓練"""
        logger.info(f"IVF-PQインデックスの訓練を開始（データ数: {len(vectors)}）")
        
        # 量子化器の作成
        quantizer = faiss.IndexFlatIP(self.dimension)
        # IVF-PQインデックスの作成
        self.index = faiss.IndexIVFPQ(quantizer, self.dimension, self.nlist, self.m, self.nbits)
        # 内積で類似度を計算するように設定
        self.index.metric_type = faiss.METRIC_INNER_PRODUCT
        # 訓練実行
        self.index.train(vectors)
        # 訓練済みデータの追加
        self.index.add(vectors)
        self.is_trained = True
        # 一時インデックスのクリア
        self.temp_index = None
        logger.info("IVF-PQインデックスの訓練が完了")
    
    def normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """ベクトルをL2正規化する"""
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        # L2ノルムを計算（各行ベクトルのノルム）
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # ゼロ除算を防ぐ
        norms = np.maximum(norms, np.finfo(vectors.dtype).tiny)
        # 正規化
        return vectors / norms
    
    def add(self, vectors: np.ndarray, metadata: list) -> None:
        if len(vectors) == 0:
            return
        
        if isinstance(vectors, list):
            vectors = np.array(vectors, dtype=np.float32)
        
        # L2正規化を適用
        normalized_vectors = self.normalize_vectors(vectors.copy())
        
        # 一時インデックスにデータを追加
        self.temp_index.add(normalized_vectors)
        
        # メタデータをSQLiteに追加
        start_id = self.db.get_metadata_count()
        self.db.add_metadata(metadata, start_id)
        
        # 十分なデータが集まったらIVF-PQの訓練を実行
        total_vectors = self.temp_index.ntotal
        if not self.is_trained and total_vectors >= self.min_training_size:
            # 全ベクトルを取得
            all_vectors = np.empty((total_vectors, self.dimension), dtype=np.float32)
            self.temp_index.reconstruct_n(0, total_vectors, all_vectors)
            # IVF-PQの初期化と訓練
            self._init_ivf_pq(all_vectors)
    
    def search(self, query_vector: np.ndarray, top_k: int = 3) -> list:
        """ベクトル検索を実行"""
        # インデックスの状態チェック
        if (self.temp_index is None or self.temp_index.ntotal == 0) and \
           (self.index is None or self.index.ntotal == 0):
            logger.warning("インデックスが空です")
            return []

        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)
        elif len(query_vector.shape) == 1:
            query_vector = query_vector.reshape(1, -1)
        
        # クエリベクトルもL2正規化
        normalized_query = self.normalize_vectors(query_vector.copy())
        
        # 使用するインデックスを決定
        if self.is_trained:
            # IVF-PQインデックスが訓練済みの場合
            self.index.nprobe = 10  # 探索するクラスタ数
            scores, indices = self.index.search(normalized_query, top_k)
        else:
            # 訓練前は一時インデックスを使用
            scores, indices = self.temp_index.search(normalized_query, top_k)
        
        # SQLiteからメタデータを取得
        metadata_list = self.db.get_metadata([int(idx) for idx in indices[0]])
        return [(metadata, score) for metadata, score in zip(metadata_list, scores[0])]

    def save(self, index_dir: str = "embeddings") -> None:
        """インデックスをプラットフォーム非依存な形式で保存（圧縮あり）"""
        index_dir = Path(index_dir)
        index_dir.mkdir(exist_ok=True)
        
        # インデックスの生ベクトルを取得（すでに正規化済み）
        vector_path = index_dir / "vectors.npz"
        
        # 使用するインデックスを決定
        active_index = self.index if self.is_trained else self.temp_index
        
        if active_index is not None and active_index.ntotal > 0:
            # numpy配列を直接取得
            vectors = np.empty((active_index.ntotal, self.dimension), dtype=np.float32)
            active_index.reconstruct_n(0, active_index.ntotal, vectors)
            # ベクトルを圧縮して保存
            np.savez_compressed(vector_path, vectors=vectors)
        else:
            # 空のインデックスの場合は空の配列を保存
            empty_vectors = np.array([], dtype=np.float32).reshape(0, self.dimension)
            np.savez_compressed(vector_path, vectors=empty_vectors)
        
        # サイズ情報をログ出力
        vector_size = os.path.getsize(vector_path) / (1024 * 1024)  # MB単位
        db_size = os.path.getsize(self.db.db_path) / (1024 * 1024)  # MB単位
        logger.info(f"インデックスを保存: {self.db.get_metadata_count()}件")
        logger.info(f"ベクトルファイルサイズ: {vector_size:.2f}MB")
        logger.info(f"データベースファイルサイズ: {db_size:.2f}MB")
        logger.debug(f"データベース: {self.db.db_path}")
        logger.debug(f"ベクトル: {vector_path}")
    
    def load(self, index_dir: str = "embeddings") -> None:
        """圧縮されたインデックスを読み込み"""
        index_dir = Path(index_dir)
        vector_path = index_dir / "vectors.npz"
        
        if not vector_path.exists():
            logger.warning("インデックスファイルが見つかりません")
            self._init_temp_index()  # 一時インデックスを初期化
            return
        
        # 圧縮されたベクトルを読み込んでインデックスを再構築
        with np.load(vector_path) as data:
            vectors = data['vectors']
            if len(vectors) >= self.min_training_size:
                # 十分なデータがある場合はIVF-PQで初期化
                self._init_ivf_pq(vectors)
            else:
                # データが少ない場合は一時インデックスとして保存
                self._init_temp_index()
                if len(vectors) > 0:
                    self.temp_index.add(vectors)
        
        # サイズ情報をログ出力
        vector_size = os.path.getsize(vector_path) / (1024 * 1024)  # MB単位
        db_size = os.path.getsize(self.db.db_path) / (1024 * 1024)  # MB単位
        logger.info(f"インデックスを読み込み: {self.db.get_metadata_count()}件")
        logger.info(f"ベクトルファイルサイズ: {vector_size:.2f}MB")
        logger.info(f"データベースファイルサイズ: {db_size:.2f}MB")
        logger.debug(f"ベクトルの形状: {vectors.shape}") 