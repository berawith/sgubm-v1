
import sqlite3
import os

def migrate_db():
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        db_path = os.path.join('src', 'infrastructure', 'database', 'sgubm.db')
        
    if not os.path.exists(db_path):
        print(f"❌ Base de datos no encontrada en {db_path}")
        return

    print(f"🚀 Iniciando migración de base de datos en: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    migrations = [
        # Tabla Payments
        "ALTER TABLE payments ADD COLUMN exchange_rate FLOAT DEFAULT 1.0",
        "ALTER TABLE payments ADD COLUMN base_amount FLOAT",
        "ALTER TABLE payments ADD COLUMN tax_amount FLOAT DEFAULT 0.0",
        "ALTER TABLE payments ADD COLUMN tax_details TEXT",
        "ALTER TABLE payments ADD COLUMN transaction_hash VARCHAR(64)",
        
        # Tabla Expenses
        "ALTER TABLE expenses ADD COLUMN base_amount FLOAT",
        "ALTER TABLE expenses ADD COLUMN exchange_rate FLOAT DEFAULT 1.0",
        "ALTER TABLE expenses ADD COLUMN tax_deductible BOOLEAN DEFAULT 1",
        "ALTER TABLE expenses ADD COLUMN tax_details TEXT",
        "ALTER TABLE expenses ADD COLUMN transaction_hash VARCHAR(64)",
        
        # Tabla Invoices
        "ALTER TABLE invoices ADD COLUMN currency VARCHAR(10) DEFAULT 'COP'",
        "ALTER TABLE invoices ADD COLUMN exchange_rate FLOAT DEFAULT 1.0",
        "ALTER TABLE invoices ADD COLUMN subtotal_amount FLOAT DEFAULT 0.0",
        "ALTER TABLE invoices ADD COLUMN tax_amount FLOAT DEFAULT 0.0",
        "ALTER TABLE invoices ADD COLUMN tax_details TEXT",
        "ALTER TABLE invoices ADD COLUMN is_fiscal BOOLEAN DEFAULT 0",
        "ALTER TABLE invoices ADD COLUMN transaction_hash VARCHAR(64)"
    ]

    for sql in migrations:
        try:
            cursor.execute(sql)
            print(f"✅ Ejecutado: {sql[:40]}...")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"ℹ️ Columna ya existe, saltando: {sql[:40]}...")
            else:
                print(f"⚠️ Error en migración: {e}")

    # Inicializar configuraciones ERP
    settings = [
        ('ERP_BASE_CURRENCY', 'USD', 'Moneda base del sistema para balance consolidado', 'erp'),
        ('ERP_REPORTING_CURRENCY', 'USD', 'Moneda de reporte ejecutivo', 'erp'),
        ('TAX_RATE_IVA_COL', '19', 'Tasa de IVA en Colombia', 'fiscal'),
        ('TAX_RATE_IVA_VEN', '16', 'Tasa de IVA en Venezuela', 'fiscal'),
        ('TAX_RATE_IGTF_VEN', '3', 'Tasa de IGTF en Venezuela', 'fiscal'),
        ('ENABLE_AUDIT_HASHING', 'true', 'Habilitar integridad por hashing SHA-256', 'security')
    ]

    for key, val, desc, cat in settings:
        try:
            cursor.execute("INSERT OR IGNORE INTO system_settings (key, value, description, category) VALUES (?, ?, ?, ?)", (key, val, desc, cat))
            print(f"✅ Configuración inicializada: {key}")
        except Exception as e:
            print(f"⚠️ Error inicializando settings: {e}")

    conn.commit()
    conn.close()
    print("✨ Migración ERP Fase 1 completada con éxito.")

if __name__ == "__main__":
    migrate_db()
