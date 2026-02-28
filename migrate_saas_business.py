
import sqlite3
import os

def migrate_saas_business_logic():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get main tenant ID
    cursor.execute("SELECT id FROM tenants WHERE subdomain = 'main'")
    res = cursor.fetchone()
    if not res:
        print("Main tenant not found. Please run migrate_saas_core.py first.")
        return
    main_tenant_id = res[0]

    tables = [
        'internet_plans', 'clients', 'payments', 'payment_promises',
        'invoices', 'audit_logs', 'support_tickets', 'expenses', 
        'whatsapp_messages', 'system_settings'
    ]

    print(f"Starting SaaS Business Logic Migration (Tenant ID: {main_tenant_id})...")

    for table in tables:
        try:
            # Add column
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE;")
            print(f"Added 'tenant_id' to '{table}'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"'tenant_id' already exists in '{table}'.")
            else:
                print(f"Error adding column to '{table}': {e}")
        
        # Update existing records
        cursor.execute(f"UPDATE {table} SET tenant_id = {main_tenant_id} WHERE tenant_id IS NULL")
        print(f"Associated existing records in '{table}' with main tenant.")

    conn.commit()
    conn.close()
    print("SaaS Business Logic Migration Completed.")

if __name__ == "__main__":
    migrate_saas_business_logic()
