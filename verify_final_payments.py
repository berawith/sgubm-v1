
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def verify_final_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*80)
    print(f"{'VERIFICACIÓN FINAL DE PAGOS (CLIENTES CRÍTICOS)':^80}")
    print("="*80)

    clients_to_check = [
        'Juan Pablo Barrios',
        'Grabiela Alvarado',
        'Leocadia Mora',
        'Roman Pernia'
    ]

    for name in clients_to_check:
        client = session.query(Client).filter(Client.legal_name.ilike(f'%{name}%')).first()
        if client:
            payments = session.query(Payment).filter(Payment.client_id == client.id).all()
            total_paid = sum(p.amount for p in payments)
            print(f"👤 {client.legal_name[:25]:<25}")
            print(f"   🆔 ID: {client.id:<4} | 🌐 IP: {client.ip_address:<15}")
            if payments:
                print(f"   ✅ PAGOS ENCONTRADOS: {len(payments)}")
                for p in payments:
                    print(f"      - ID {p.id}: ${p.amount:,.0f} | Fecha: {p.payment_date}")
                print(f"   💰 TOTAL ACUMULADO: ${total_paid:,.0f}")
            else:
                print(f"   ❌ NO TIENE PAGOS REGISTRADOS")
        else:
            print(f"👤 {name:<25} | ❌ CLIENTE NO ENCONTRADO")
        print("-" * 80)

    session.close()

if __name__ == "__main__":
    verify_final_payments()
