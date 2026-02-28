
import sqlite3
import os

def migrate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Starting Support Resolution migration...")

    columns = [
        ("actual_failure", "TEXT"),
        ("resolution_details", "TEXT"),
        ("technicians", "TEXT"),
        ("materials_used", "TEXT"),
        ("support_cost", "FLOAT DEFAULT 0.0"),
        ("admin_observations", "TEXT"),
        ("support_date", "DATETIME")
    ]

    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE support_tickets ADD COLUMN {col_name} {col_type};")
            print(f"Added '{col_name}' to 'support_tickets' table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"'{col_name}' already exists.")
            else:
                print(f"Error adding column '{col_name}': {e}")

    conn.commit()
    conn.close()
    print("Support migration completed.")

if __name__ == "__main__":
    migrate()
