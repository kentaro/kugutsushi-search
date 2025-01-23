import sqlite3
from pathlib import Path
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "embeddings/metadata.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()
    
    def _init_db(self):
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
    
    def clear(self):
        """全データの削除"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM metadata")
            conn.execute("VACUUM")  # ファイルサイズを最適化
    
    def add_metadata(self, metadata_list: List[Dict], start_id: int = 0) -> int:
        """メタデータの一括追加"""
        with sqlite3.connect(self.db_path) as conn:
            for i, metadata in enumerate(metadata_list, start=start_id):
                conn.execute(
                    "INSERT INTO metadata (id, text, file, page) VALUES (?, ?, ?, ?)",
                    (i, metadata["text"], metadata["file"], metadata["page"])
                )
        return len(metadata_list)
    
    def get_metadata(self, ids: List[int]) -> List[Dict]:
        """IDリストに対応するメタデータを取得"""
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" * len(ids))
            query = f"SELECT id, text, file, page FROM metadata WHERE id IN ({placeholders})"
            cursor = conn.execute(query, ids)
            return [
                {
                    "text": row[1],
                    "file": row[2],
                    "page": row[3]
                }
                for row in cursor.fetchall()
            ]
    
    def get_all_metadata(self) -> List[Dict]:
        """全メタデータを取得"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, text, file, page FROM metadata ORDER BY id")
            return [
                {
                    "text": row[1],
                    "file": row[2],
                    "page": row[3]
                }
                for row in cursor.fetchall()
            ]
    
    def get_metadata_count(self) -> int:
        """メタデータの総数を取得"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM metadata")
            return cursor.fetchone()[0]
    
    def get_file_list(self) -> List[str]:
        """登録されているファイル一覧を取得"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT file FROM metadata")
            return [row[0] for row in cursor.fetchall()] 