
import sqlite3
import os

def populate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Nuevos sub-módulos para poblar
    new_modules = [
        'dashboard',
        'clients:list', 'clients:import', 'clients:trash',
        'finance:payments', 'finance:invoices', 'finance:promises', 
        'finance:reports', 'finance:expenses',
        'routers:list', 'routers:monitoring',
        'whatsapp:chats', 'whatsapp:config',
        'system:users', 'system:rbac',
        'collector-finance'
    ]

    print("🚀 Populating new granular modules...")

    # Obtener roles existentes (excepto admin que siempre tiene todo)
    cursor.execute("SELECT DISTINCT role_name FROM role_permissions")
    roles = [row[0] for row in rows if row[0]] if (rows := cursor.fetchall()) else ['collector', 'partner', 'technical', 'secretary']

    for role in roles:
        for mod in new_modules:
            # Verificar si ya existe
            cursor.execute("SELECT 1 FROM role_permissions WHERE role_name = ? AND module = ?", (role, mod))
            if not cursor.fetchone():
                # Por defecto, si es admin tiene todo, si no, depende de la lógica anterior.
                # Para simplificar la migración, daremos permisos básicos de vista si era un módulo padre que ya tenían.
                
                can_view = 0
                if role in ['admin', 'administradora']:
                    can_view = 1
                elif role == 'collector' and mod.startswith('finance:'):
                    can_view = 1
                elif role == 'technical' and (mod.startswith('clients:') or mod.startswith('routers:')):
                    can_view = 1
                elif role == 'secretary' and (mod.startswith('clients:') or mod.startswith('finance:')):
                    can_view = 1
                
                # Insertar nuevo registro
                cursor.execute("""
                    INSERT INTO role_permissions (role_name, module, can_view, can_create, can_edit, can_delete, can_print, can_revert)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (role, mod, can_view, can_view, can_view, 0, can_view, 0))
                print(f"  ✅ Added {mod} for role {role}")

    conn.commit()
    conn.close()
    print("✨ Population completed.")

if __name__ == '__main__':
    populate()
