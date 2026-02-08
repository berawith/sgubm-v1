
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Añadir el path del proyecto para importar modelos
sys.path.append(os.getcwd())

try:
    from src.infrastructure.database.models import Payment, Client
except ImportError:
    print("Error: No se pudieron importar los modelos. Asegúrate de ejecutar desde la raíz del proyecto.")
    sys.exit(1)

def audit_payments():
    database_url = 'sqlite:///sgubm.db'
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*60)
    print("INFORME DE AUDITORÍA DE PAGOS DUPLICADOS (BASE DE DATOS)")
    print("="*60)

    # 1. Buscar pagos con la misma REFERENCIA (si no está vacía)
    print("\n[1] Verificando Referencias Duplicadas...")
    dup_refs = session.query(
        Payment.reference, 
        func.count(Payment.id).label('qty')
    ).filter(Payment.reference != '', Payment.reference != None)\
     .group_by(Payment.reference)\
     .having(func.count(Payment.id) > 1).all()

    if not dup_refs:
        print("   ✅ No se encontraron referencias duplicadas.")
    else:
        for ref, qty in dup_refs:
            print(f"   ⚠️ Referencia '{ref}' encontrada {qty} veces:")
            payments = session.query(Payment).filter(Payment.reference == ref).all()
            for p in payments:
                client = session.query(Client).get(p.client_id)
                name = client.legal_name if client else "Desconocido"
                print(f"      - ID Pago: {p.id}, Cliente: {name}, Fecha: {p.payment_date}, Monto: {p.amount}")

    # 2. Buscar pagos para el mismo cliente con el mismo monto en el mismo día
    print("\n[2] Verificando Pagos Idénticos (Mismo Cliente, Monto y Día)...")
    
    # Query compleja para encontrar duplicados por fecha (solo el día), cliente y monto
    # Usamos date() de SQLite (func.date en SQLAlchemy)
    identical_payments = session.query(
        Payment.client_id,
        Payment.amount,
        func.date(Payment.payment_date).label('p_date'),
        func.count(Payment.id).label('qty')
    ).group_by(
        Payment.client_id, 
        Payment.amount, 
        func.date(Payment.payment_date)
    ).having(func.count(Payment.id) > 1).all()

    if not identical_payments:
        print("   ✅ No se encontraron pagos idénticos en el mismo día.")
    else:
        for cid, amt, pdate, qty in identical_payments:
            client = session.query(Client).get(cid)
            name = client.legal_name if client else "Desconocido"
            print(f"   ⚠️ Posible Duplicado: {name} - ${amt} el día {pdate} ({qty} registros)")
            
            # Detalle de los pagos
            details = session.query(Payment).filter(
                Payment.client_id == cid,
                Payment.amount == amt,
                func.date(Payment.payment_date) == pdate
            ).all()
            for d in details:
                print(f"      - ID Pago: {d.id}, Referencia: {d.reference}, Fecha Exacta: {d.payment_date}")

    # 3. Resumen General
    total_payments = session.query(func.count(Payment.id)).scalar()
    print("\n" + "="*60)
    print(f"Resumen: {total_payments} pagos totales revisados.")
    print("="*60)

    session.close()

if __name__ == "__main__":
    audit_payments()
