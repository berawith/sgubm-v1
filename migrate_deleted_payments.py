
import sqlite3
import os

def migrate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Creating deleted_payments table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS deleted_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_id INTEGER,
        client_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'COP',
        payment_date DATETIME,
        payment_method TEXT,
        reference TEXT,
        notes TEXT,
        deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        deleted_by TEXT,
        reason TEXT,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )
    ''')

    conn.commit()
    conn.close()
    print("Migration completed successfully")

if __name__ == '__main__':
    migrate()
