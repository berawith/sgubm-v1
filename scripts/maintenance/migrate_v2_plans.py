
import logging
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, InternetPlan

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PlanMigration")

DB_PATH = 'sgubm.db'

def run_migration():
    logger.info("🚀 Iniciando migración a Planes Centralizados...")
    
    # 1. ACTUALIZACIÓN DE SCHEMA (SQL RAW para SQLite)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # A. Crear tabla internet_plans
        logger.info("1. Creando tabla 'internet_plans'...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS internet_plans (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            download_speed INTEGER NOT NULL,
            upload_speed INTEGER NOT NULL,
            monthly_price FLOAT DEFAULT 0.0,
            currency VARCHAR(10) DEFAULT 'COP',
            service_type VARCHAR(50) DEFAULT 'pppoe',
            mikrotik_profile VARCHAR(100),
            burst_limit VARCHAR(50),
            burst_threshold VARCHAR(50),
            burst_time VARCHAR(50),
            priority INTEGER DEFAULT 8,
            aggregation VARCHAR(20),
            created_at DATETIME
        )
        """)
        
        # B. Agregar columna plan_id a clients
        logger.info("2. Verificando columna 'plan_id' en 'clients'...")
        cursor.execute("PRAGMA table_info(clients)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'plan_id' not in columns:
            cursor.execute("ALTER TABLE clients ADD COLUMN plan_id INTEGER REFERENCES internet_plans(id)")
            logger.info("   ✅ Columna 'plan_id' agregada.")
        else:
            logger.info("   ⬇️ Columna 'plan_id' ya existía.")
            
        conn.commit()
    except Exception as e:
        logger.error(f"❌ Error en Schema Migration: {e}")
        conn.close()
        return
    finally:
        conn.close()

    # 2. MIGRACIÓN DE DATOS (SQLAlchemy)
    db = get_db()
    session = db.session
    
    try:
        clients = session.query(Client).all()
        logger.info(f"3. Analizando {len(clients)} clientes para extraer planes...")
        
        # Diccionario para evitar duplicados: key -> InternetPlan obj
        # Key: (name, price, download, upload)
        discovered_plans = {}
        
        migrated_clients = 0
        
        for client in clients:
            # Normalizar datos del plan actual
            p_name = client.plan_name or f"Plan {client.download_speed}"
            p_price = client.monthly_fee or 0.0
            
            # Intentar parsear velocidades (suelen venir como "10M/10M" o "10240k")
            def parse_speed(speed_str):
                if not speed_str: return 0
                s = speed_str.lower().replace('k', '').replace('m', '000').split('/')[0]
                try:
                    return int(float(s))
                except:
                    return 0

            down = parse_speed(client.download_speed)
            up = parse_speed(client.upload_speed)
            
            # Key única para identificar el plan
            plan_key = (p_name.strip(), p_price, down, up)
            
            if plan_key not in discovered_plans:
                # Verificar si ya existe en DB (por si corremos el script 2 veces)
                existing = session.query(InternetPlan).filter_by(
                    name=p_name, monthly_price=p_price, download_speed=down
                ).first()
                
                if existing:
                    discovered_plans[plan_key] = existing
                else:
                    # Crear nuevo plan
                    new_plan = InternetPlan(
                        name=p_name,
                        monthly_price=p_price,
                        download_speed=down,
                        upload_speed=up,
                        service_type=client.service_type or 'pppoe',
                        mikrotik_profile=p_name # Asumimos que el nombre del plan es el perfil MK
                    )
                    session.add(new_plan)
                    session.flush() # Para obtener ID
                    discovered_plans[plan_key] = new_plan
                    logger.info(f"   ✨ Nuevo Plan detectado: {p_name} (${p_price})")
            
            # Asignar Plan al Cliente
            plan = discovered_plans[plan_key]
            
            if client.plan_id != plan.id:
                client.plan_id = plan.id
                migrated_clients += 1
        
        session.commit()
        logger.info("=======================================")
        logger.info(f"TOTAL: {len(discovered_plans)} Planes creados/detectados.")
        logger.info(f"CLIENTES MIGRADOS: {migrated_clients}")
        logger.info("=======================================")
        
    except Exception as e:
        logger.error(f"❌ Error en Data Migration: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()
