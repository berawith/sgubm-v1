
import sqlite3
import os

def populate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Populating finance sub-modules...")

    roles = ['admin', 'administradora', 'partner', 'technical', 'secretary', 'collector']
    submodules = [
        'finance:payments', 
        'finance:invoices', 
        'finance:promises', 
        'finance:reports', 
        'finance:expenses'
    ]

    for role in roles:
        # Get permissions of the original 'finance' module for this role if it exists
        cursor.execute("SELECT can_view, can_create, can_edit, can_delete FROM role_permissions WHERE role_name = ? AND module = 'finance'", (role,))
        base_perm = cursor.fetchone()
        
        if not base_perm:
            # Defaults if 'finance' doesn't exist for some reason
            base_perm = (1 if role in ['admin', 'administradora', 'secretary', 'collector'] else 0, 0, 0, 0)
        
        can_view, can_create, can_edit, can_delete = base_perm
        
        # Admin gets everything
        is_admin = role in ['admin', 'administradora']
        
        for sub in submodules:
            # Check if sub-module already exists
            cursor.execute("SELECT id FROM role_permissions WHERE role_name = ? AND module = ?", (role, sub))
            if cursor.fetchone():
                print(f"ℹ️ {role} already has {sub}, skipping.")
                continue
                
            # Default values for print and revert
            can_print = 1 if is_admin or role == 'secretary' or (role == 'collector' and sub == 'finance:payments') else 0
            can_revert = 1 if is_admin else 0
            
            # Special case for collector: can create payments but not others
            current_can_create = can_create if sub == 'finance:payments' else 0
            if is_admin: current_can_create = 1

            cursor.execute("""
                INSERT INTO role_permissions (role_name, module, can_view, can_create, can_edit, can_delete, can_print, can_revert)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (role, sub, can_view, current_can_create, can_edit if is_admin else 0, can_delete if is_admin else 0, can_print, can_revert))
            print(f"✅ Added {sub} for {role}")

    conn.commit()
    conn.close()
    print("✨ Sub-modules population completed.")

if __name__ == "__main__":
    populate()
