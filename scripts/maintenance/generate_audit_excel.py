
import os
import sys
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from collections import defaultdict
from datetime import datetime

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice
except ImportError:
    print("Error imports")
    sys.exit(1)

def generate_audit_excel():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    clients = session.query(Client).all()
    all_payments = session.query(Payment).all()
    
    # Mapeo de ultimo pago por cliente
    last_p_map = defaultdict(lambda: "Nunca")
    for p in all_payments:
        if last_p_map[p.client_id] == "Nunca" or p.payment_date > last_p_map[p.client_id]:
            last_p_map[p.client_id] = p.payment_date

    # --- CATEGORIA 1: IPS DUPLICADAS ---
    ip_records = []
    ip_groups = defaultdict(list)
    for c in clients:
        if c.ip_address:
            ip_groups[c.ip_address.split('/')[0]].append(c)
    
    for ip, group in ip_groups.items():
        if len(group) > 1:
            for c in group:
                ip_records.append({
                    'IP': ip,
                    'ID': c.id,
                    'Nombre en Sistema': c.legal_name,
                    'Codigo': c.subscriber_code,
                    'Status': c.status,
                    'Ultimo Pago': last_p_map[c.id],
                    'Accion Sugerida': 'FUSIONAR O ELIMINAR'
                })

    # --- CATEGORIA 2: CODIGOS DUPLICADOS ---
    code_records = []
    code_groups = defaultdict(list)
    for c in clients:
        if c.subscriber_code:
            code_groups[c.subscriber_code].append(c)
    
    for code, group in code_groups.items():
        if len(group) > 1:
            for c in group:
                code_records.append({
                    'CODIGO': code,
                    'ID': c.id,
                    'Nombre en Sistema': c.legal_name,
                    'IP': c.ip_address,
                    'Status': c.status,
                    'Ultimo Pago': last_p_map[c.id]
                })

    # --- CATEGORIA 3: NOMBRES GENERICOS (Sq-...) ---
    generic_records = []
    for c in clients:
        if c.legal_name and (c.legal_name.startswith('Sq-') or c.legal_name.startswith('pppoe-')):
            generic_records.append({
                'ID': c.id,
                'Nombre Generico': c.legal_name,
                'IP': c.ip_address,
                'Codigo': c.subscriber_code,
                'Ultimo Pago': last_p_map[c.id],
                'Nota': 'Probable residuo de escaneo MikroTik'
            })

    # Escribir a Excel
    output_path = 'AUDITORIA_DUPLICADOS_SGUBM.xlsx'
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        if ip_records:
            pd.DataFrame(ip_records).to_excel(writer, sheet_name='IPs Duplicadas', index=False)
        if code_records:
            pd.DataFrame(code_records).to_excel(writer, sheet_name='Codigos Duplicados', index=False)
        if generic_records:
            pd.DataFrame(generic_records).to_excel(writer, sheet_name='Nombres Genericos', index=False)

    print(f"Excel generado: {os.path.abspath(output_path)}")
    session.close()

if __name__ == "__main__":
    generate_audit_excel()
