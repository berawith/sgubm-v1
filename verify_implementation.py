
import sqlite3
import os

def check_db():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking 'collector_transfers' table...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collector_transfers';")
    if cursor.fetchone():
        print("✅ Table 'collector_transfers' exists.")
        cursor.execute("PRAGMA table_info(collector_transfers);")
        columns = [c[1] for c in cursor.fetchall()]
        print(f"Columns: {', '.join(columns)}")
    else:
        print("❌ Table 'collector_transfers' does NOT exist.")

    print("\nChecking RBAC permissions for 'collector' on 'collector-finance'...")
    cursor.execute("""
        SELECT can_view, can_create, can_edit, can_delete 
        FROM role_permissions 
        WHERE role_name='collector' AND module='collector-finance';
    """)
    perm = cursor.fetchone()
    if perm:
        print(f"✅ Permissions found: View={perm[0]}, Create={perm[1]}, Edit={perm[2]}, Delete={perm[3]}")
    else:
        print("❌ Permissions for 'collector' on 'collector-finance' NOT found.")

    print("\nChecking RBAC permissions for 'collector' on 'clients'...")
    cursor.execute("""
        SELECT can_view, can_create, can_edit, can_delete 
        FROM role_permissions 
        WHERE role_name='collector' AND module='clients';
    """)
    perm = cursor.fetchone()
    if perm:
        print(f"✅ Permissions found: View={perm[0]}, Create={perm[1]}, Edit={perm[2]}, Delete={perm[3]}")
    else:
        print("❌ Permissions for 'collector' on 'clients' NOT found.")

    conn.close()

if __name__ == "__main__":
    check_db()
