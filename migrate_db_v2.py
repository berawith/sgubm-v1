
import sqlite3
import os

def migrate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Starting database migration...")

    # 1. Add assigned_collector_id to clients
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN assigned_collector_id INTEGER REFERENCES users(id) ON DELETE SET NULL;")
        print("✅ Added 'assigned_collector_id' to 'clients' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ 'assigned_collector_id' already exists in 'clients' table.")
        else:
            print(f"❌ Error adding column to 'clients': {e}")

    # 2. Add user_id to expenses
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;")
        print("✅ Added 'user_id' to 'expenses' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ 'user_id' already exists in 'expenses' table.")
        else:
            print(f"❌ Error adding column to 'expenses': {e}")

    # 3. Add router_id to expenses
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN router_id INTEGER REFERENCES routers(id) ON DELETE CASCADE;")
        print("✅ Added 'router_id' to 'expenses' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ 'router_id' already exists in 'expenses' table.")
        else:
            print(f"❌ Error adding column to 'expenses': {e}")

    conn.commit()
    conn.close()
    print("✨ Migration completed.")

if __name__ == "__main__":
    migrate()
