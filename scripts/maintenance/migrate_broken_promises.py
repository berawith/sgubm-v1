import sqlite3
import os

def migrate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"Base de datos no encontrada en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Añadiendo columna 'broken_promises_count' a la tabla 'clients'...")
        cursor.execute("ALTER TABLE clients ADD COLUMN broken_promises_count INTEGER DEFAULT 0")
        conn.commit()
        print("Migración completada con éxito.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("La columna 'broken_promises_count' ya existe.")
        else:
            print(f"Error operativo: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
