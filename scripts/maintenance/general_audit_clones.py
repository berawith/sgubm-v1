
import os
import sys
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from collections import defaultdict

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Router
except ImportError:
    print("Error: No se pudieron importar los modelos.")
    sys.exit(1)

def general_scan():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*80)
    print("REPORTE DE AUDITORÍA: POSIBLES CLONES Y DUPLICADOS")
    print("="*80)

    # 1. Buscar IPs duplicadas
    print("\n[🔍] ESCANEANDO IPS DUPLICADAS...")
    print("-" * 30)
    # Agrupamos por IP
    ip_groups = defaultdict(list)
    all_clients = session.query(Client).all()
    for c in all_clients:
        if c.ip_address:
            clean_ip = c.ip_address.split('/')[0]
            ip_groups[clean_ip].append(c)

    found_ip_dupes = False
    for ip, clients in ip_groups.items():
        if len(clients) > 1:
            found_ip_dupes = True
            print(f"⚠️ IP DUPLICADA: {ip}")
            for c in clients:
                print(f"   - ID: {c.id} | Nombre: {c.legal_name} | Código: {c.subscriber_code} | Router: {c.router_id}")
            print("")
    
    if not found_ip_dupes:
        print("✅ No se encontraron IPs compartidas por diferentes clientes.")

    # 2. Buscar Códigos de Suscriptor duplicados
    print("\n[🔍] ESCANEANDO CÓDIGOS DE SUSCRIPTOR DUPLICADOS...")
    print("-" * 30)
    code_groups = defaultdict(list)
    for c in all_clients:
        if c.subscriber_code:
            code_groups[c.subscriber_code].append(c)
    
    found_code_dupes = False
    for code, clients in code_groups.items():
        if len(clients) > 1:
            found_code_dupes = True
            print(f"⚠️ CÓDIGO DUPLICADO: {code}")
            for c in clients:
                print(f"   - ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address}")
            print("")
    
    if not found_code_dupes:
        print("✅ No se encontraron códigos de suscriptor duplicados.")

    # 3. Buscar clientes con nombres muy similares (basado en primer nombre)
    print("\n[🔍] ESCANEANDO NOMBRES SIMILARES (POSIBLES CLONES)...")
    print("-" * 30)
    name_groups = defaultdict(list)
    for c in all_clients:
        if c.legal_name:
            first_part = c.legal_name.split()[0].lower() if c.legal_name.split() else c.legal_name.lower()
            name_groups[first_part].append(c)
    
    found_name_clones = False
    for part, clients in name_groups.items():
        if len(clients) > 1:
            # Solo mostrar si tienen diferentes IPs o códigos
            unique_ips = set(c.ip_address for c in clients)
            if len(unique_ips) > 1 or len(clients) > 3: # Si hay muchos con el mismo primer nombre
                found_name_clones = True
                print(f"❓ POSIBLES CLONES (Nombre similar): '{part.capitalize()}'")
                for c in clients:
                    print(f"   - ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | Cod: {c.subscriber_code}")
                print("")

    print("=" * 80)
    session.close()

if __name__ == "__main__":
    general_scan()
