
import logging
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BillingMigration")

DB_PATH = 'sgubm.db'

def run_migration():
    logger.info("🚀 Iniciando migración de Facturación V1...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # A. Crear tabla Invoices
        logger.info("1. Creando tabla 'invoices'...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id),
            issue_date DATETIME NOT NULL,
            due_date DATETIME NOT NULL,
            total_amount FLOAT DEFAULT 0.0,
            status VARCHAR(20) DEFAULT 'unpaid',
            pdf_path VARCHAR(255),
            created_at DATETIME,
            updated_at DATETIME
        )
        """)
        
        # B. Crear tabla Invoice Items
        logger.info("2. Creando tabla 'invoice_items'...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES invoices(id),
            description VARCHAR(200) NOT NULL,
            amount FLOAT NOT NULL
        )
        """)
            
        conn.commit()
        logger.info("✅ Tablas de facturación creadas exitosamente.")
        
    except Exception as e:
        logger.error(f"❌ Error en Billing Schema Migration: {e}")
        conn.close()
        return
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
