
import sqlite3
import os

def migrate():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Verificando tabla internet_plans...")
    
    # Check if router_id exists in internet_plans
    cursor.execute("PRAGMA table_info(internet_plans)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'router_id' not in columns:
        print("Agregando columna router_id a internet_plans...")
        cursor.execute("ALTER TABLE internet_plans ADD COLUMN router_id INTEGER REFERENCES routers(id)")
    
    conn.commit()
    conn.close()
    print("Migración completada con éxito.")

if __name__ == "__main__":
    migrate()
