
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Añadir el path del proyecto para importar modelos
sys.path.append(os.getcwd())

try:
    from src.infrastructure.database.models import Payment
except ImportError:
    print("Error: No se pudieron importar los modelos.")
    sys.exit(1)

def check_payments(client_id):
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"\nRevisando historial de pagos registrados hoy para el Cliente ID: {client_id}")
    print("-" * 70)

    # Buscar pagos realizados hoy (2026-02-06)
    payments = session.query(Payment).filter(
        Payment.client_id == client_id,
        Payment.payment_date >= '2026-02-06 00:00:00'
    ).all()

    if not payments:
        print("❌ No se encontraron pagos registrados el día de hoy para este cliente.")
        # Ver el último pago histórico por si acaso
        last_payment = session.query(Payment).filter(Payment.client_id == client_id).order_by(Payment.payment_date.desc()).first()
        if last_payment:
            print(f"\nÚltimo pago registrado históricamente:")
            print(f" - ID Pago: {last_payment.id}, Monto: ${last_payment.amount}, Fecha: {last_payment.payment_date}, Ref: {last_payment.reference}")
    else:
        print(f"Se encontraron {len(payments)} pago(s) el día de hoy:")
        for p in payments:
            print(f" ✅ ID Pago: {p.id}")
            print(f"    Monto: ${p.amount}")
            print(f"    Fecha: {p.payment_date}")
            print(f"    Referencia: {p.reference or 'N/A'}")
            print(f"    Método: {p.payment_method}")
            print(f"    Notas: {p.notes or 'Sin notas'}")
            print("-" * 30)

    session.close()

if __name__ == "__main__":
    # El ID de Leocadia Mora es 508 según la consulta anterior
    check_payments(508)
