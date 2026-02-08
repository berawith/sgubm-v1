"""
Script para diagnosticar y arreglar problemas con la tabla internet_plans
"""
import sqlite3
import sys

def diagnose_plans_table():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()
        
        print("🔍 Diagnosticando tabla internet_plans...")
        print()
        
        # Ver si la tabla existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='internet_plans'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ La tabla 'internet_plans' NO EXISTE")
            print("   Necesitas ejecutar init_db.py para crear las tablas")
            conn.close()
            return False
        
        print("✅ La tabla 'internet_plans' existe")
        print()
        
        # Ver la estructura de la tabla
        cursor.execute("PRAGMA table_info(internet_plans)")
        columns = cursor.fetchall()
       
        print("📋 Columnas existentes:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        print()
        
        # Contar planes
        cursor.execute("SELECT COUNT(*) FROM internet_plans")
        count = cursor.fetchone()[0]
        print(f"📊 Total de planes: {count}")
        print()
        
        # Verificar columnas necesarias
        column_names = [col[1] for col in columns]
        required_columns = [
            'id', 'name', 'download_speed', 'upload_speed', 
            'monthly_price', 'currency', 'service_type'
        ]
        
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if missing_columns:
            print(f"⚠️  Columnas faltantes: {', '.join(missing_columns)}")
            print("   Necesitas ejecutar una migración")
            conn.close()
            return False
        
        print("✅ Todas las columnas necesarias están presentes")
        
        # Verificar si hay errores con NULLs
        cursor.execute("SELECT * FROM internet_plans LIMIT 5")
        plans = cursor.fetchall()
        
        if plans:
            print()
            print(f"📦 Primeros {len(plans)} planes:")
            for plan in plans:
                print(f"   - ID: {plan[0]}, Nombre: {plan[1]}")
        
        conn.close()
        return True
        
    except sqlite3.OperationalError as e:
        print(f"❌ Error de SQLite: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = diagnose_plans_table()
    sys.exit(0 if success else 1)
