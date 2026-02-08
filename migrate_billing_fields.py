import sqlite3
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'sgubm.db'

def migrate_router_fields():
    print("🔄 Iniciando migración de campos de facturación en Routers...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    columns_to_add = [
        ('billing_day', 'INTEGER', '1'),
        ('grace_period', 'INTEGER', '5'),
        ('cut_day', 'INTEGER', '10')
    ]
    
    for col_name, col_type, default_val in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE routers ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
            print(f"✅ Columna '{col_name}' agregada exitosamente.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️ Columna '{col_name}' ya existe. Saltando.")
            else:
                print(f"❌ Error agregando column '{col_name}': {e}")

    conn.commit()
    conn.close()
    print("✅ Migración completada.")

if __name__ == "__main__":
    migrate_router_fields()
