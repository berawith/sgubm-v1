
import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir el path del proyecto para importar modelos
sys.path.append(os.getcwd())

try:
    from src.infrastructure.database.models import Client
except ImportError:
    print("Error: No se pudieron importar los módulos.")
    sys.exit(1)

def carefully_clean_dynamic_ips():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*80)
    print("LIMPIEZA CUIDADOSA DE ETIQUETA 'DINÁMICA' EN DIRECCIONES IP")
    print("="*80)

    # 1. Identificar clientes
    # Usamos iLike para capturar variaciones como 'dinamica', 'Dinámica', etc.
    targets = session.query(Client).filter(Client.ip_address.ilike('Dinámica%')).all()
    
    if not targets:
        print("✅ No se encontraron clientes con la etiqueta 'Dinámica' actualmente.")
        session.close()
        return

    print(f"Se encontraron {len(targets)} clientes que serán actualizados.")
    print("-" * 50)

    updated_count = 0
    for client in targets:
        old_ip = client.ip_address
        # Cambiamos a None (NULL en la base de datos)
        # Esto es más seguro que un string vacío para evitar colisiones de 'empty string'
        client.ip_address = None
        updated_count += 1
        print(f"🔹 ID: {client.id:<5} | {client.legal_name[:30]:<30} | {old_ip} -> [VACIADO]")

    # 2. Confirmar cambios
    try:
        session.commit()
        print("-" * 50)
        print(f"✅ ÉXITO: Se han limpiado {updated_count} registros cuidadosamente.")
        print("Efecto: El campo IP ahora está vacío (NULL). El sistema ya no los confundirá como duplicados.")
        print("El próximo escaneo de MikroTik intentará llenar este campo con la IP real detectada.")
    except Exception as e:
        session.rollback()
        print(f"❌ ERROR durante la actualización: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    carefully_clean_dynamic_ips()
