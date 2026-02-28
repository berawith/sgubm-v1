
import sqlite3
import os

def clean():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Módulos antiguos que deben ser eliminados
    old_modules = ['clients', 'finance', 'routers', 'system', 'whatsapp']

    print("🚀 Cleaning up old modules...")
    for mod in old_modules:
        cursor.execute("DELETE FROM role_permissions WHERE module = ?", (mod,))
        print(f"  🗑️ Deleted old module: {mod} ({cursor.rowcount} rows)")

    conn.commit()
    conn.close()
    print("✨ Cleanup completed.")

if __name__ == '__main__':
    clean()
