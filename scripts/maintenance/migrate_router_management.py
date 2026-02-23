from src.infrastructure.database.db_manager import init_db
from sqlalchemy import text, inspect

def migrate():
    print("Iniciando migración de Routers...")
    engine = init_db()
    
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('routers')]
    
    with engine.connect() as conn:
        if 'management_method' not in columns:
            print("Agregando columna management_method...")
            conn.execute(text("ALTER TABLE routers ADD COLUMN management_method VARCHAR(50) DEFAULT 'mixed'"))
        
        if 'pppoe_ranges' not in columns:
            print("Agregando columna pppoe_ranges...")
            conn.execute(text("ALTER TABLE routers ADD COLUMN pppoe_ranges TEXT"))
            
        if 'dhcp_ranges' not in columns:
            print("Agregando columna dhcp_ranges...")
            conn.execute(text("ALTER TABLE routers ADD COLUMN dhcp_ranges TEXT"))
            
    print("Migración completada exitosamente.")

if __name__ == "__main__":
    migrate()
