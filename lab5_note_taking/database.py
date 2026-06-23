import sqlite3

DB_FILE = "notes.db"

def init_db():
    """初始化 SQLite 資料庫，建立隨手筆記本的資料表。"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 建立筆記資料表
    c.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_note(user_id: int, content: str):
    """新增一筆筆記至資料庫。"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO notes (user_id, content) VALUES (?, ?)",
        (user_id, content)
    )
    conn.commit()
    conn.close()

def get_notes(user_id: int) -> list:
    """取得特定使用者的所有筆記，依建立時間由新到舊排序。"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT id, content, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def delete_note(user_id: int, note_id: int) -> bool:
    """刪除指定 ID 且屬於該使用者的筆記。回傳刪除是否成功。"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "DELETE FROM notes WHERE id = ? AND user_id = ?",
        (note_id, user_id)
    )
    affected = c.rowcount > 0
    conn.commit()
    conn.close()
    return affected
