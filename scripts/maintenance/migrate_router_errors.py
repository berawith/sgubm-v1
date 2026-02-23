import sqlite3
import os

db_path = 'sgubm.db'

def migrate():
    if not os.path.exists(db_path):
        print(f"Error: Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns_to_add = [
        ('last_online_at', 'DATETIME'),
        ('last_error', 'TEXT')
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE routers ADD COLUMN {col_name} {col_type}")
            print(f"Column '{col_name}' added successfully.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column '{col_name}' already exists.")
            else:
                print(f"Error adding column '{col_name}': {e}")

    conn.commit()
    conn.close()
    print("Migration finished.")

if __name__ == "__main__":
    migrate()
