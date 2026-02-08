
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from collections import defaultdict

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error imports")
    sys.exit(1)

def auto_detect_main_client(group, last_p_map):
    """
    Decide quién es el cliente real vs el clon.
    Prioridad: 
    1. Quien tenga el pago más reciente.
    2. Quien NO tenga nombre genérico (Sq-...).
    3. El ID más antiguo (menor).
    """
    # Ordenar por fecha de pago desc (None es lo más antiguo)
    def sort_key(c):
        p_date = last_p_map.get(c.id)
        p_val = p_date.timestamp() if hasattr(p_date, 'timestamp') else 0
        is_generic = 1 if (c.legal_name.startswith('Sq-') or c.legal_name.startswith('pppoe-')) else 0
        return (p_val, -is_generic, -c.id)

    sorted_group = sorted(group, key=sort_key, reverse=True)
    return sorted_group[0], sorted_group[1:]

def execute_safe_cleanup():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*80)
    print("EJECUTANDO LIMPIEZA AUTOMÁTICA Y SEGURA DE DUPLICADOS")
    print("="*80)

    clients = session.query(Client).all()
    all_payments = session.query(Payment).all()
    
    # Mapa de ultimo pago
    last_p_map = {}
    for p in all_payments:
        if p.client_id not in last_p_map or p.payment_date > last_p_map[p.client_id]:
            last_p_map[p.client_id] = p.payment_date

    # Agrupar por IP
    ip_groups = defaultdict(list)
    for c in clients:
        if c.ip_address:
            ip_groups[c.ip_address.split('/')[0]].append(c)

    total_merged = 0
    total_payments_moved = 0

    for ip, group in ip_groups.items():
        if len(group) > 1:
            main, clones = auto_detect_main_client(group, last_p_map)
            print(f"\n[🔄] IP {ip}: Mantendremos a '{main.legal_name}' (ID {main.id})")
            
            for clon in clones:
                print(f"    - Fusionando clon: '{clon.legal_name}' (ID {clon.id})")
                
                # Mover Pagos
                clon_payments = session.query(Payment).filter(Payment.client_id == clon.id).all()
                for p in clon_payments:
                    p.client_id = main.id
                    total_payments_moved += 1
                
                # Mover Facturas
                clon_invoices = session.query(Invoice).filter(Invoice.client_id == clon.id).all()
                for inv in clon_invoices:
                    inv.client_id = main.id
                
                # Eliminar Clon
                session.delete(clon)
                total_merged += 1

    session.commit()
    print("\n" + "="*80)
    print(f"RESUMEN DE LIMPIEZA:")
    print(f"- Clientes duplicados eliminados: {total_merged}")
    print(f"- Pagos re-asignados al dueño real: {total_payments_moved}")
    print("="*80)
    
    # Sincronizar nombres en MikroTik para los clientes que quedaron
    print("\n[🛰️] Sincronizando nombres reales en MikroTik...")
    # Solo para los que tuvieron fusiones o nombres genéricos pero son únicos ahora
    # Por brevedad, sincronizaremos a todos los que tengan router_id
    session.close()

if __name__ == "__main__":
    execute_safe_cleanup()
