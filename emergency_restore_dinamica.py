
import os
import sys
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice
except ImportError:
    print("Error")
    sys.exit(1)

def emergency_restore():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- INICIANDO RESTAURACIÓN DE EMERGENCIA POR ERROR DE FUSIÓN 'DINÁMICA' ---")

    try:
        # Leer el excel de auditoria para recuperar los datos
        df_ips = pd.read_excel('AUDITORIA_DUPLICADOS_SGUBM.xlsx', sheet_name='IPs Duplicadas')
        
        # Filtrar solo los que tienen IP "Dinámica" y que NO son el ID 9 (que fue el que quedó vivo)
        # También incluiremos a Grabiela por si quedó algo pendiente.
        to_restore = df_ips[ (df_ips['IP'] == 'Dinámica') & (df_ips['ID'] != 9) ]
        
        print(f"Se encontraron {len(to_restore)} personas para restaurar de la lista 'Dinámica'.")

        for _, row in to_restore.iterrows():
            # Verificar si ya existe (por si acaso estuve restaurando por partes)
            exists = session.query(Client).filter(Client.subscriber_code == row['Codigo']).first()
            if exists:
                print(f"Skipping {row['Nombre en Sistema']} - Ya existe.")
                continue

            # Crear el cliente nuevamente
            # Nota: Algunos datos como router_id se perdieron en el excel, intentaremos recuperarlos o poner el 1 por defecto
            new_c = Client(
                subscriber_code=row['Codigo'],
                legal_name=row['Nombre en Sistema'],
                ip_address='Dinámica',
                status=row['Status'],
                router_id=1, # Default a PRINCIPAL, el usuario podrá corregirlo si era otro
                username=row['Nombre en Sistema'].replace(' ', ''),
                account_balance=0.0
            )
            session.add(new_c)
            session.flush()
            
            print(f"✅ Restaurado: {row['Nombre en Sistema']} (Cod: {row['Codigo']})")

        session.commit()
    except Exception as e:
        print(f"Error durante restauración: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    emergency_restore()
