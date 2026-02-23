"""
Migration: Crear tabla de operaciones pendientes para sincronización MikroTik
Permite guardar operaciones cuando el router está offline y ejecutarlas después
"""
import sqlite3
from datetime import datetime

DB_PATH = 'src/infrastructure/database/sgubm.db'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de operaciones pendientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            client_id INTEGER NOT NULL,
            router_id INTEGER NOT NULL,
            target_status TEXT,
            ip_address TEXT,
            operation_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            attempts INTEGER DEFAULT 0,
            last_attempt TIMESTAMP,
            error_message TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (router_id) REFERENCES routers(id) ON DELETE CASCADE
        )
    ''')
    
    # Índices para búsqueda rápida
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pending_ops_router 
        ON pending_operations(router_id, status)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pending_ops_client 
        ON pending_operations(client_id, status)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pending_ops_created 
        ON pending_operations(created_at)
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ Tabla 'pending_operations' creada exitosamente")
    print("✅ Índices creados para búsqueda rápida")

if __name__ == '__main__':
    migrate()
