"""メタデータ管理 - SQLiteによるテキスト・ファイル情報の永続化"""

import sqlite3
from pathlib import Path
import logging
from typing import List, Dict
import unicodedata

logger = logging.getLogger(__name__)


class Database:
    """SQLiteによるメタデータ管理

    スキーマ:
        id: INTEGER PRIMARY KEY（ベクトルインデックスと対応）
        text: TEXT（ページ本文）
        file: TEXT（PDFファイル名）
        page: INTEGER（ページ番号、0-indexed）

    注意: add_metadata()はバッファに追加するだけで、flush()を呼ぶまでDBに保存されない。
    これによりベクトルとメタデータの整合性を保つ。
    """

    def __init__(self, db_path: str = "embeddings/metadata.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._buffer = []  # メタデータバッファ
        self._buffer_start_id = 0
        self._init_db()

    def _init_db(self) -> None:
        """データベースとテーブルの初期化"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY,
                    text TEXT NOT NULL,
                    file TEXT NOT NULL,
                    page INTEGER NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_page ON metadata(file, page)")

    def clear(self) -> None:
        """全データの削除"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM metadata")
            conn.execute("VACUUM")

    def add_metadata(self, metadata_list: List[Dict], start_id: int = 0) -> int:
        """メタデータをバッファに追加（flush()まで保存されない）"""
        if not self._buffer:
            self._buffer_start_id = start_id
        self._buffer.extend(metadata_list)
        return len(metadata_list)

    def flush(self) -> int:
        """バッファをDBに書き込み"""
        if not self._buffer:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT INTO metadata (id, text, file, page) VALUES (?, ?, ?, ?)",
                [(self._buffer_start_id + i, m["text"], m["file"], m["page"]) for i, m in enumerate(self._buffer)]
            )
        count = len(self._buffer)
        self._buffer = []
        self._buffer_start_id = 0
        return count

    def get_metadata(self, ids: List[int]) -> List[Dict]:
        """IDリストに対応するメタデータを取得（順序維持）"""
        if not ids:
            return []
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" * len(ids))
            query = f"SELECT id, text, file, page FROM metadata WHERE id IN ({placeholders})"
            cursor = conn.execute(query, ids)
            rows = {row[0]: {"text": row[1], "file": row[2], "page": row[3]} for row in cursor.fetchall()}
            return [rows.get(i, {}) for i in ids if i in rows]

    def get_all_metadata(self) -> List[Dict]:
        """全メタデータを取得（ID順）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT text, file, page FROM metadata ORDER BY id")
            return [{"text": row[0], "file": row[1], "page": row[2]} for row in cursor.fetchall()]

    def get_all_texts(self) -> List[str]:
        """全テキストをID順で取得（BM25用）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT text FROM metadata ORDER BY id")
            return [row[0] for row in cursor.fetchall()]

    def get_metadata_count(self) -> int:
        """メタデータの総数を取得（バッファ含む）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM metadata")
            db_count = cursor.fetchone()[0]
        return db_count + len(self._buffer)

    def _normalize(self, text: str) -> str:
        """Unicode正規化（NFC形式に統一）"""
        return unicodedata.normalize('NFC', text)

    def get_file_list(self) -> List[str]:
        """登録されているファイル一覧を取得（NFC正規化済み）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT file FROM metadata")
            return [self._normalize(row[0]) for row in cursor.fetchall()]

    def get_metadata_by_file(self, filename: str) -> List[Dict]:
        """特定ファイルのメタデータをページ順で取得

        ファイル名はNFC/NFD両形式で検索し、Unicode正規化の違いを吸収する
        """
        normalized = self._normalize(filename)
        with sqlite3.connect(self.db_path) as conn:
            # まずNFC正規化した名前で検索
            cursor = conn.execute(
                "SELECT text, page FROM metadata WHERE file = ? ORDER BY page, id",
                (normalized,)
            )
            results = cursor.fetchall()

            # 見つからなければNFD形式でも試す
            if not results:
                nfd = unicodedata.normalize('NFD', filename)
                cursor = conn.execute(
                    "SELECT text, page FROM metadata WHERE file = ? ORDER BY page, id",
                    (nfd,)
                )
                results = cursor.fetchall()

            # それでも見つからなければ元の形式で試す
            if not results:
                cursor = conn.execute(
                    "SELECT text, page FROM metadata WHERE file = ? ORDER BY page, id",
                    (filename,)
                )
                results = cursor.fetchall()

            return [{"text": row[0], "page": row[1]} for row in results]
