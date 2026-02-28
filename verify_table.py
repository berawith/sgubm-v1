from src.infrastructure.database.db_manager import get_db
from sqlalchemy import inspect

def verify_table():
    db = get_db()
    inspector = inspect(db._engine)
    tables = inspector.get_table_names()
    print(f"Tablas encontradas: {tables}")
    if 'payment_details' in tables:
        print("✅ La tabla 'payment_details' fue creada correctamente.")
        
        # Verificar columnas
        columns = [c['name'] for c in inspector.get_columns('payment_details')]
        print(f"Columnas en payment_details: {columns}")
    else:
        print("❌ La tabla 'payment_details' NO existe.")

if __name__ == "__main__":
    verify_table()
