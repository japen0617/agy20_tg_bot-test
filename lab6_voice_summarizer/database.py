import sqlite3
from typing import List, Tuple, Optional

DB_FILE = "notes.db"

def init_db() -> None:
    """初始化 SQLite 資料庫，建立隨手筆記與語音筆記的資料表。"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        
        # 建立一般文字筆記資料表
        c.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 建立語音筆記資料表
        c.execute('''
            CREATE TABLE IF NOT EXISTS voice_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_id TEXT,
                transcription TEXT,
                summary TEXT,
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def add_note(user_id: int, content: str) -> None:
    """新增一筆文字筆記至資料庫。"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO notes (user_id, content) VALUES (?, ?)",
            (user_id, content)
        )
        conn.commit()

def get_notes(user_id: int) -> List[Tuple[int, str, str]]:
    """取得特定使用者的所有文字筆記，依建立時間由新到舊排序。"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, content, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return c.fetchall()

def delete_note(user_id: int, note_id: int) -> bool:
    """刪除指定 ID 且屬於該使用者的文字筆記。回傳刪除是否成功。"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id)
        )
        conn.commit()
        return c.rowcount > 0

# --- 語音筆記相關 API ---

def add_voice_note(user_id: int, file_id: str, transcription: str, summary: str, duration: int) -> None:
    """新增一筆語音筆記至資料庫。"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO voice_notes (user_id, file_id, transcription, summary, duration) VALUES (?, ?, ?, ?, ?)",
            (user_id, file_id, transcription, summary, duration)
        )
        conn.commit()

def get_voice_notes(user_id: int) -> List[Tuple[int, str, str, str, int, str]]:
    """取得特定使用者的所有語音筆記，欄位順序：id, file_id, transcription, summary, duration, created_at"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, file_id, transcription, summary, duration, created_at FROM voice_notes WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return c.fetchall()

def get_voice_note_by_id(user_id: int, note_id: int) -> Optional[Tuple[int, str, str, str, int, str]]:
    """依 ID 取得語音筆記詳細資訊。"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, file_id, transcription, summary, duration, created_at FROM voice_notes WHERE id = ? AND user_id = ?",
            (note_id, user_id)
        )
        return c.fetchone()

def delete_voice_note(user_id: int, note_id: int) -> bool:
    """刪除特定使用者的特定語音筆記。"""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "DELETE FROM voice_notes WHERE id = ? AND user_id = ?",
            (note_id, user_id)
        )
        conn.commit()
        return c.rowcount > 0
