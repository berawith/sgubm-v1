
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice
except ImportError:
    print("Error")
    sys.exit(1)

def undo_grabiela_merge():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- RESTAURANDO A GRABIELA ALVARADO PISCURI ---")

    # 1. Crear nuevamente el cliente Grabiela (Datos obtenidos del reporte de auditoría)
    # Usaremos el código CLI-0524 que es el que tenía el pago más reciente.
    new_grabiela = Client(
        subscriber_code='CLI-0524',
        legal_name='Grabiela Alvarado Piscuri',
        ip_address='177.77.70.23',
        router_id=1, # PRINCIPAL (según el reporte)
        status='active', # La pondremos activa ya que pagó
        monthly_fee=90000.0,
        username='GrabielaAlvarado',
        account_balance=0.0
    )
    session.add(new_grabiela)
    session.flush() # Para obtener el ID nuevo
    
    new_id = new_grabiela.id
    print(f"✅ Re-creada Grabiela Alvarado con nuevo ID: {new_id}")

    # 2. Identificar y devolver pagos
    # Sabemos que Grabiela pagó hoy aprox a las 16:21. 
    # Buscamos pagos en la cuenta de Roman Pernia (ID 71) que coincidan con ese monto y fecha.
    stolen_payments = session.query(Payment).filter(
        Payment.client_id == 71,
        Payment.amount == 90000.0,
        Payment.payment_date >= '2026-02-06 16:00:00'
    ).all()

    for p in stolen_payments:
        p.client_id = new_id
        print(f"✅ Pago ID {p.id} devuelto a Grabiela.")

    # 3. Devolver facturas
    # Las facturas que se movieron a Roman que originalmente eran de Grabiela
    # (Por simplicidad, moveremos las que coincidan con el monto)
    stolen_invoices = session.query(Invoice).filter(
        Invoice.client_id == 71,
        Invoice.total_amount == 90000.0
    ).all()
    
    for inv in stolen_invoices:
        inv.client_id = new_id
        print(f"✅ Factura ID {inv.id} devuelta a Grabiela.")

    session.commit()
    print("\n--- RESTAURACIÓN COMPLETADA ---")
    session.close()

if __name__ == "__main__":
    undo_grabiela_merge()
