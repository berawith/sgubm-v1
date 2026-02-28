
import sqlite3
import os

def repair():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Repairing Admin permissions...")
    
    # Otorgar TODO a admin y administradora
    admin_roles = ['admin', 'administradora']
    for role in admin_roles:
        cursor.execute("""
            UPDATE role_permissions 
            SET can_view = 1, can_create = 1, can_edit = 1, can_delete = 1, can_print = 1, can_revert = 1
            WHERE role_name = ?
        """, (role,))
        print(f"  ✅ Updated {cursor.rowcount} modules for role: {role}")

    # Asegurar que todos los módulos tengan los campos can_print y can_revert habilitados para ser editados
    # En realidad, el problema era que el to_dict no los mandaba, pero ya lo arreglamos.
    
    conn.commit()
    conn.close()
    print("✨ Repair completed.")

if __name__ == '__main__':
    repair()
