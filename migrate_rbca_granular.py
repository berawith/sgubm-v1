
import sqlite3
import os

def migrate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Starting granular RBAC migration...")

    # 1. Add can_print to role_permissions
    try:
        cursor.execute("ALTER TABLE role_permissions ADD COLUMN can_print BOOLEAN DEFAULT 0;")
        print("✅ Added 'can_print' to 'role_permissions' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ 'can_print' already exists in 'role_permissions' table.")
        else:
            print(f"❌ Error adding 'can_print' to 'role_permissions': {e}")

    # 2. Add can_revert to role_permissions
    try:
        cursor.execute("ALTER TABLE role_permissions ADD COLUMN can_revert BOOLEAN DEFAULT 0;")
        print("✅ Added 'can_revert' to 'role_permissions' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ 'can_revert' already exists in 'role_permissions' table.")
        else:
            print(f"❌ Error adding 'can_revert' to 'role_permissions': {e}")

    conn.commit()
    conn.close()
    print("✨ Migration completed.")

if __name__ == "__main__":
    migrate()
