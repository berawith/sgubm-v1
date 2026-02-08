
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Payment, Client, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error: No se pudieron importar los módulos.")
    sys.exit(1)

def deep_check():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- CHEQUEO PROFUNDO DE PAGOS Y MIKROTIK ---")
    
    # 1. Pagos de Juan Pablo Barrios hoy
    print("\n[1] Pagos de Juan Pablo Barrios (ID 86) hoy:")
    p_jp = session.query(Payment).filter(Payment.client_id == 86, Payment.payment_date >= '2026-02-06 00:00:00').all()
    if p_jp:
        for p in p_jp:
            print(f"ID Pago: {p.id} | Monto: {p.amount} | Ref: {p.reference} | Notas: {p.notes}")
    else:
        print("No se encontraron pagos hoy para Juan Pablo Barrios.")

    # 2. Revisar el Router 4 (donde está Leocadia) para ver esa IP
    router = session.query(Router).get(4)
    if router and router.status == 'online':
        print(f"\n[2] Consultando IP 77.16.10.239 directamente en Router {router.alias}...")
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # Buscar en Secrets y Queues
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                found_q = [q for q in queues if '77.16.10.239' in q.get('target', '')]
                for q in found_q:
                    print(f"MikroTik Queue: Name={q.get('name')} | Target={q.get('target')} | Comment={q.get('comment')}")
                
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                found_s = [s for s in secrets if s.get('remote-address') == '77.16.10.239']
                for s in found_s:
                    print(f"MikroTik Secret: Name={s.get('name')} | RemoteIP={s.get('remote-address')} | Comment={s.get('comment')}")
            finally:
                adapter.disconnect()
    
    session.close()

if __name__ == "__main__":
    deep_check()
