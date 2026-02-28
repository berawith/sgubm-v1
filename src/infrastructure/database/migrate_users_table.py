import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'sgubm.db')

def upgrade_users_table():
    print(f"Iniciando actualización de la tabla 'users' en {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    new_columns = {
        'identity_document': 'VARCHAR(50)',
        'phone_number': 'VARCHAR(50)',
        'email': 'VARCHAR(100)',
        'address': 'TEXT',
        'profit_percentage': 'FLOAT DEFAULT 0.0',
        'bonus_amount': 'FLOAT DEFAULT 0.0',
        'assigned_zone': 'VARCHAR(100)'
    }
    
    added_count = 0
    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print(f"✅ Columna '{col_name}' añadida con éxito.")
                added_count += 1
            except Exception as e:
                print(f"❌ Error al añadir columna '{col_name}': {e}")
        else:
            print(f"ℹ️ Columna '{col_name}' ya existe, omitiendo.")
            
    conn.commit()
    conn.close()
    
    print(f"Actualización completada. {added_count} columnas añadidas.")

if __name__ == '__main__':
    upgrade_users_table()
