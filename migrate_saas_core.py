
import sqlite3
import os

def migrate_saas_core():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Starting SaaS Core Migration...")

    # 1. Create tenants table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subdomain TEXT UNIQUE,
        brand_color TEXT DEFAULT '#4f46e5',
        logo_path TEXT,
        is_active BOOLEAN DEFAULT 1,
        plan_type TEXT DEFAULT 'basic',
        settings TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        trial_ends_at DATETIME
    )
    ''')
    print("Table 'tenants' created or already exists.")

    # 2. Add tenant_id to users and routers
    for table in ['users', 'routers']:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE;")
            print(f"Added 'tenant_id' to '{table}' table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"'tenant_id' already exists in '{table}'.")
            else:
                print(f"Error adding column to '{table}': {e}")

    # 3. Create initial tenant if it doesn't exist
    cursor.execute("SELECT id FROM tenants WHERE subdomain = 'main' OR id = 1")
    main_tenant = cursor.fetchone()
    
    if not main_tenant:
        cursor.execute("INSERT INTO tenants (name, subdomain) VALUES ('ISP Central', 'main')")
        main_tenant_id = cursor.lastrowid
        print(f"Created initial tenant with ID: {main_tenant_id}")
    else:
        main_tenant_id = main_tenant[0]

    # 4. Associate existing users and routers with the main tenant
    cursor.execute(f"UPDATE users SET tenant_id = {main_tenant_id} WHERE tenant_id IS NULL")
    cursor.execute(f"UPDATE routers SET tenant_id = {main_tenant_id} WHERE tenant_id IS NULL")
    print("Existing users and routers associated with main tenant.")

    conn.commit()
    conn.close()
    print("SaaS Core Migration Completed.")

if __name__ == "__main__":
    migrate_saas_core()
