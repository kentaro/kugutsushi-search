"""BM25インデックス - SQLite + 語彙削減による軽量キーワード検索"""

from typing import List, Dict, Tuple
import sqlite3
import logging
from pathlib import Path
import re
import math
import struct

logger = logging.getLogger(__name__)


class BM25Indexer:
    """SQLiteベースのBM25インデックス（効率的なスキーマ）

    - postingsリストをバイナリblobで保存（行数を大幅削減）
    - 低頻度語を削除して語彙サイズを削減
    - メモリ使用量を最小化
    """

    def __init__(self, db_path: str = "embeddings/bm25.db", min_df: int = 2):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.k1 = 1.5
        self.b = 0.75
        self.min_df = min_df  # 最低出現文書数（これ未満の語は無視）
        self._conn = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value REAL
            );
            CREATE TABLE IF NOT EXISTS doc_lens (
                doc_id INTEGER PRIMARY KEY,
                length INTEGER
            );
            CREATE TABLE IF NOT EXISTS terms (
                term TEXT PRIMARY KEY,
                df INTEGER,
                postings BLOB
            );
        """)
        conn.commit()

    def _encode_postings(self, postings: Dict[int, int]) -> bytes:
        """postings dict を効率的なバイナリにエンコード"""
        # フォーマット: [doc_id (4bytes), tf (2bytes)] の繰り返し
        data = []
        for doc_id, tf in sorted(postings.items()):
            data.append(struct.pack('<IH', doc_id, min(tf, 65535)))
        return b''.join(data)

    def _decode_postings(self, blob: bytes) -> List[Tuple[int, int]]:
        """バイナリから postings をデコード"""
        result = []
        for i in range(0, len(blob), 6):
            doc_id, tf = struct.unpack('<IH', blob[i:i+6])
            result.append((doc_id, tf))
        return result

    def tokenize(self, text: str) -> List[str]:
        """日本語テキストをトークン化（単語 + 2-gram）"""
        words = re.findall(r'[\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+', text.lower())
        tokens = []
        for word in words:
            tokens.append(word)
            if len(word) >= 2:
                for i in range(len(word) - 1):
                    tokens.append(word[i:i + 2])
        return tokens

    def add(self, texts: List[str]) -> None:
        """テキストを追加（インクリメンタル）"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COALESCE(MAX(doc_id), -1) + 1 FROM doc_lens")
        start_id = cursor.fetchone()[0]

        # メモリ内で一時的に集計
        doc_lens_data = []
        term_postings: Dict[str, Dict[int, int]] = {}

        for i, text in enumerate(texts):
            doc_id = start_id + i
            tokens = self.tokenize(text)
            doc_lens_data.append((doc_id, len(tokens)))

            term_counts: Dict[str, int] = {}
            for token in tokens:
                term_counts[token] = term_counts.get(token, 0) + 1

            for term, tf in term_counts.items():
                if term not in term_postings:
                    term_postings[term] = {}
                term_postings[term][doc_id] = tf

        # doc_lens挿入
        cursor.executemany("INSERT INTO doc_lens VALUES (?, ?)", doc_lens_data)

        # terms更新（既存のpostingsとマージ）
        for term, new_postings in term_postings.items():
            cursor.execute("SELECT df, postings FROM terms WHERE term = ?", (term,))
            row = cursor.fetchone()

            if row:
                old_df, old_blob = row
                old_postings = dict(self._decode_postings(old_blob))
                old_postings.update(new_postings)
                new_df = len(old_postings)
                new_blob = self._encode_postings(old_postings)
                cursor.execute("UPDATE terms SET df = ?, postings = ? WHERE term = ?",
                             (new_df, new_blob, term))
            else:
                new_blob = self._encode_postings(new_postings)
                cursor.execute("INSERT INTO terms VALUES (?, ?, ?)",
                             (term, len(new_postings), new_blob))

        # 統計更新
        cursor.execute("SELECT COUNT(*), SUM(length) FROM doc_lens")
        count, total_len = cursor.fetchone()
        avgdl = total_len / count if count > 0 else 0

        cursor.execute("INSERT OR REPLACE INTO stats VALUES ('corpus_size', ?)", (count,))
        cursor.execute("INSERT OR REPLACE INTO stats VALUES ('avgdl', ?)", (avgdl,))

        conn.commit()
        logger.info(f"BM25: {len(texts)}件追加（合計{count}件）")

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """BM25スコアで検索"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM stats WHERE key = 'corpus_size'")
        row = cursor.fetchone()
        if not row:
            return []
        corpus_size = int(row[0])

        cursor.execute("SELECT value FROM stats WHERE key = 'avgdl'")
        avgdl = cursor.fetchone()[0]

        query_tokens = set(self.tokenize(query))
        if not query_tokens:
            return []

        # doc_lensをキャッシュ（初回のみ）
        cursor.execute("SELECT doc_id, length FROM doc_lens")
        doc_lens = {row[0]: row[1] for row in cursor.fetchall()}

        scores: Dict[int, float] = {}

        for token in query_tokens:
            cursor.execute("SELECT df, postings FROM terms WHERE term = ?", (token,))
            row = cursor.fetchone()
            if not row:
                continue

            df, blob = row
            if df < self.min_df:
                continue

            idf = math.log((corpus_size - df + 0.5) / (df + 0.5) + 1)
            postings = self._decode_postings(blob)

            for doc_id, tf in postings:
                doc_len = doc_lens.get(doc_id, avgdl)
                term_score = idf * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
                )
                scores[doc_id] = scores.get(doc_id, 0) + term_score

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]

    @property
    def corpus_size(self) -> int:
        cursor = self._get_conn().cursor()
        cursor.execute("SELECT value FROM stats WHERE key = 'corpus_size'")
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    @property
    def vocab_size(self) -> int:
        cursor = self._get_conn().cursor()
        cursor.execute("SELECT COUNT(*) FROM terms")
        return cursor.fetchone()[0]

    def save(self, index_dir: str = "embeddings") -> None:
        conn = self._get_conn()
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        logger.info(f"BM25を保存: {self.corpus_size}件, 語彙{self.vocab_size}語")

    def load(self, index_dir: str = "embeddings") -> None:
        old_json = Path(index_dir) / "bm25_stats.json"
        if old_json.exists() and self.corpus_size == 0:
            logger.info("旧形式(JSON)からSQLiteへ移行中...")
            self._migrate_from_json(old_json)
            return

        if self.corpus_size > 0:
            logger.info(f"BM25を読み込み: {self.corpus_size}件, 語彙{self.vocab_size}語")

    def _migrate_from_json(self, json_path: Path) -> None:
        """旧JSONからSQLiteへ移行（効率的なスキーマ + 語彙削減）"""
        import json

        logger.info("JSON読み込み中...")
        data = json.loads(json_path.read_text(encoding='utf-8'))

        conn = self._get_conn()
        cursor = conn.cursor()

        # doc_lens
        logger.info("doc_lens移行中...")
        doc_lens_data = [(i, length) for i, length in enumerate(data["doc_lens"])]
        cursor.executemany("INSERT INTO doc_lens VALUES (?, ?)", doc_lens_data)
        conn.commit()

        # terms（語彙削減 + バイナリ圧縮）
        logger.info("転置インデックス移行中（語彙削減適用）...")
        inverted = data["inverted_index"]
        total_terms = len(inverted)
        kept_terms = 0
        batch = []

        for i, (term, postings) in enumerate(inverted.items()):
            df = len(postings)
            # 低頻度語を削除（min_df未満）
            if df < self.min_df:
                continue

            postings_dict = {int(doc_id): tf for doc_id, tf in postings.items()}
            blob = self._encode_postings(postings_dict)
            batch.append((term, df, blob))
            kept_terms += 1

            if len(batch) >= 10000:
                cursor.executemany("INSERT INTO terms VALUES (?, ?, ?)", batch)
                conn.commit()
                batch = []
                if kept_terms % 100000 == 0:
                    logger.info(f"  {kept_terms:,}語処理済み...")

        if batch:
            cursor.executemany("INSERT INTO terms VALUES (?, ?, ?)", batch)

        # 統計
        cursor.execute("INSERT OR REPLACE INTO stats VALUES ('corpus_size', ?)", (data["corpus_size"],))
        cursor.execute("INSERT OR REPLACE INTO stats VALUES ('avgdl', ?)", (data["avgdl"],))
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        # 旧ファイルをリネーム
        json_path.rename(json_path.with_suffix('.json.old'))

        pruned = total_terms - kept_terms
        db_size = self.db_path.stat().st_size / (1024 * 1024)
        logger.info(f"移行完了: {self.corpus_size}件, 語彙{kept_terms:,}語 (削除{pruned:,}語), {db_size:.1f}MB")

    def prune_vocabulary(self, min_df: int = 3) -> int:
        """低頻度語を削除して軽量化"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM terms WHERE df < ?", (min_df,))
        to_delete = cursor.fetchone()[0]
        cursor.execute("DELETE FROM terms WHERE df < ?", (min_df,))
        conn.commit()
        conn.execute("VACUUM")
        logger.info(f"語彙削減: {to_delete:,}語削除")
        return to_delete

    def verify_integrity(self, metadata_count: int) -> Tuple[bool, str]:
        if self.corpus_size != metadata_count:
            return False, f"不整合: BM25 {self.corpus_size}件 != メタデータ{metadata_count}件"
        return True, f"整合: {self.corpus_size}件"
