"""
Migración: Añadir columnas local_address y remote_address a internet_plans
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('sgubm.db')
    cursor = conn.cursor()
    
    try:
        print("🔧 Añadiendo columnas faltantes a internet_plans...")
        
        # Verificar si ya existen
        cursor.execute("PRAGMA table_info(internet_plans)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'local_address' not in columns:
            cursor.execute("ALTER TABLE internet_plans ADD COLUMN local_address VARCHAR(50)")
            print("✅ Columna 'local_address' añadida")
        else:
            print("ℹ️  Columna 'local_address' ya existe")
        
        if 'remote_address' not in columns:
            cursor.execute("ALTER TABLE internet_plans ADD COLUMN remote_address VARCHAR(50)")
            print("✅ Columna 'remote_address' añadida")
        else:
            print("ℹ️  Columna 'remote_address' ya existe")
        
        conn.commit()
        print()
        print("✅ Migración completada exitosamente!")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
