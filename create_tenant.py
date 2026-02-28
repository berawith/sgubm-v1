
import sqlite3
import os
from werkzeug.security import generate_password_hash

def create_new_tenant(name, subdomain, admin_username, admin_password, brand_color='#4f46e5'):
    db_path = 'sgubm.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print(f"Provisioning new tenant: {name} ({subdomain})...")
        
        # 1. Create Tenant
        cursor.execute(
            "INSERT INTO tenants (name, subdomain, brand_color, is_active) VALUES (?, ?, ?, ?)",
            (name, subdomain, brand_color, 1)
        )
        tenant_id = cursor.lastrowid
        print(f"✅ Tenant created with ID: {tenant_id}")

        # 2. Create Admin User for this Tenant
        hashed_pw = generate_password_hash(admin_password, method='scrypt')
        cursor.execute(
            "INSERT INTO users (tenant_id, username, password_hash, role, full_name, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, admin_username, hashed_pw, 'admin', f"Admin {name}", 1)
        )
        print(f"✅ Admin user '{admin_username}' created for tenant.")

        # 3. Create a default Router for the new tenant (Optional but helpful)
        cursor.execute(
            "INSERT INTO routers (tenant_id, name, ip_address, status) VALUES (?, ?, ?, ?)",
            (tenant_id, f"Core {name}", "192.168.1.1", "offline")
        )
        print(f"✅ Default router created for tenant.")

        conn.commit()
        print(f"\n🚀 Success! Tenant '{name}' is ready.")
        print(f"Access via: http://{subdomain}.localhost:5000 (if subdomains are mapped)")
        print(f"Credentials: {admin_username} / {admin_password}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error creating tenant: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Example Usage
    import sys
    if len(sys.argv) > 1:
        name = sys.argv[1]
        subdomain = sys.argv[2]
        user = sys.argv[3]
        pw = sys.argv[4]
        color = sys.argv[5] if len(sys.argv) > 5 else '#4f46e5'
        create_new_tenant(name, subdomain, user, pw, color)
    else:
        print("Usage: python create_tenant.py <name> <subdomain> <admin_user> <admin_pass> [brand_color]")
        print("Example: python create_tenant.py 'ISP Norte' 'norte' 'admin_norte' 'pass123' '#e11d48'")
