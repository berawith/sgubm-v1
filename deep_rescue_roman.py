
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def deep_search_all_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- BÚSQUEDA EXHAUSTIVA DE PAGOS DE ROMAN ---")
    
    # 1. Buscar a Roman oficial
    roman = session.query(Client).filter(Client.legal_name.ilike('%Roman Pernia%')).first()
    
    # 2. Buscar en TODOS los pagos cualquier referencia a Roman
    all_payments = session.query(Payment).all()
    found_count = 0
    
    for p in all_payments:
        match = False
        # Buscar en notas
        if p.notes and ('roman' in p.notes.lower() or 'pernia' in p.notes.lower()):
            match = True
        
        # Si encontramos algo, informamos
        if match:
            found_count += 1
            current_owner = session.query(Client).get(p.client_id)
            print(f"✅ Pago Encontrado (ID: {p.id})")
            print(f"   Monto: ${p.amount} | Fecha: {p.payment_date}")
            print(f"   Nota: {p.notes}")
            print(f"   Dueño actual: {current_owner.legal_name if current_owner else 'Desconocido'} (ID: {p.client_id})")
            
            if roman and p.client_id != roman.id:
                print(f"   👉 Reasignando a {roman.legal_name} (ID: {roman.id})...")
                p.client_id = roman.id

    if found_count == 0:
        print("❌ No se encontraron pagos con el nombre 'Roman' o 'Pernia' en las notas.")
    else:
        session.commit()
        print(f"\nSe procesaron {found_count} pagos.")

    session.close()

if __name__ == "__main__":
    deep_search_all_payments()
