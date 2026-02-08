
import os
import sys
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    sys.exit(1)

def build_full_system_map():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    routers = session.query(Router).filter(Router.status == 'online').all()
    all_physical_data = []

    for r in routers:
        print(f"Escaneando {r.alias}...")
        adapter = MikroTikAdapter()
        if adapter.connect(r.host_address, r.api_username, r.api_password, r.api_port):
            try:
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                for s in secrets:
                    all_physical_data.append({
                        'Router': r.alias,
                        'Service': 'PPPoE',
                        'Name': s.get('name'),
                        'IP': s.get('remote-address'),
                        'Comment': s.get('comment'),
                        'Disabled': s.get('disabled') == 'true'
                    })
                
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                for q in queues:
                    all_physical_data.append({
                        'Router': r.alias,
                        'Service': 'Queue',
                        'Name': q.get('name'),
                        'IP': q.get('target', '').split('/')[0],
                        'Comment': q.get('comment'),
                        'Disabled': q.get('disabled') == 'true'
                    })
            finally:
                adapter.disconnect()

    df_physical = pd.DataFrame(all_physical_data)
    
    # 2. Obtener datos de la BD
    db_clients = session.query(Client).all()
    db_data = []
    for c in db_clients:
        r = session.query(Router).get(c.router_id)
        db_data.append({
            'ID': c.id,
            'Name_DB': c.legal_name,
            'User_DB': c.username,
            'IP_DB': c.ip_address,
            'Router_DB': r.alias if r else 'NA',
            'Status_DB': c.status
        })
    df_db = pd.DataFrame(db_data)

    # 3. Guardar todo en un Excel de comparación
    with pd.ExcelWriter('MAPA_TOTAL_SISTEMA.xlsx') as writer:
        df_physical.to_excel(writer, sheet_name='MikroTik Real', index=False)
        df_db.to_excel(writer, sheet_name='Base de Datos', index=False)

    print("Mapa total generado en MAPA_TOTAL_SISTEMA.xlsx")
    session.close()

if __name__ == "__main__":
    build_full_system_map()
