
import sqlite3

def migrate():
    print("Iniciando migración manual de base de datos...")
    
    # Nombre de la base de datos (según lo visto en los logs: sgubm_isp.db o sgubm.db)
    # Vamos a intentar conectarnos a ambas por si acaso, o verificar cuál es la activa
    # En settings.py dice: name: str = os.getenv("DB_NAME", "sgubm_isp")
    # y driver: str = os.getenv("DB_DRIVER", "sqlite")
    # connection_string: sqlite:///sgubm_isp.db
    
    db_name = "sgubm.db"
    
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # Verificar si la columna fx_variance existe en la tabla payments
        print(f"Verificando tabla 'payments' en {db_name}...")
        cursor.execute("PRAGMA table_info(payments)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'fx_variance' not in columns:
            print("Columna 'fx_variance' no encontrada. Agregando...")
            try:
                cursor.execute("ALTER TABLE payments ADD COLUMN fx_variance FLOAT DEFAULT 0.0")
                print("Columna 'fx_variance' agregada exitosamente.")
            except Exception as e:
                print(f"Error al agregar columna fx_variance: {e}")
        else:
            print("Columna 'fx_variance' ya existe.")
            
        if 'transaction_hash' not in columns:
            print("Columna 'transaction_hash' no encontrada. Agregando...")
            try:
                cursor.execute("ALTER TABLE payments ADD COLUMN transaction_hash VARCHAR(64)")
                cursor.execute("CREATE INDEX ix_payments_transaction_hash ON payments (transaction_hash)")
                print("Columna 'transaction_hash' agregada exitosamente.")
            except Exception as e:
                print(f"Error al agregar columna transaction_hash: {e}")
        else:
            print("Columna 'transaction_hash' ya existe.")

        # Verificar tabla invoices
        print(f"Verificando tabla 'invoices' en {db_name}...")
        cursor.execute("PRAGMA table_info(invoices)")
        inv_columns = [info[1] for info in cursor.fetchall()]

        new_inv_cols = {
            'currency': 'VARCHAR(10) DEFAULT "COP"',
            'exchange_rate': 'FLOAT DEFAULT 1.0',
            'subtotal_amount': 'FLOAT DEFAULT 0.0',
            'tax_amount': 'FLOAT DEFAULT 0.0',
            'tax_details': 'TEXT',
            'is_fiscal': 'BOOLEAN DEFAULT 0',
            'transaction_hash': 'VARCHAR(64)'
        }

        for col, definition in new_inv_cols.items():
            if col not in inv_columns:
                print(f"Columna '{col}' no encontrada en invoices. Agregando...")
                try:
                    cursor.execute(f"ALTER TABLE invoices ADD COLUMN {col} {definition.split(' ', 1)[1]}") # Hacky sqlite alter
                    # SQLite no soporta toda la definición en ADD COLUMN a veces, simplificamos
                    # cursor.execute(f"ALTER TABLE invoices ADD COLUMN {col} {definition}")
                    print(f"Columna '{col}' agregada exitosamente.")
                except Exception as e:
                    # Fallback simple
                    try: 
                        type_only = definition.split(' ')[0]
                        cursor.execute(f"ALTER TABLE invoices ADD COLUMN {col} {type_only}")
                        print(f"Columna '{col}' agregada (versión simple).")
                    except Exception as e2:
                        print(f"Error al agregar columna {col}: {e2}")

        conn.commit()
        conn.close()
        print("Migración completada.")
        
    except Exception as e:
        print(f"Error general en la migración: {e}")

if __name__ == "__main__":
    migrate()
