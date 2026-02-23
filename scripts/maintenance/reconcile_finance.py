
import logging
import re
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.database.models import Client, Payment, DeletedPayment, Invoice, AuditLog

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("reconciliation")

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

def find_ghost_payments():
    print("\n=== [1] BUSCANDO PAGOS FANTASMA (LOGS SIN REGISTRO) ===")
    logs = session.query(AuditLog).filter(
        AuditLog.operation == 'payment_registered'
    ).order_by(AuditLog.timestamp.desc()).all()
    
    ghosts = []
    for l in logs:
        # Extract amount and reference from description
        # Example: "Pago registrado vía transfer. Ref: 5899 (Monto: 90000.0)"
        ref_match = re.search(r'Ref: (\w+)', l.description)
        amount_match = re.search(r'Monto: ([\d.]+)', l.description)
        
        if ref_match:
            ref = ref_match.group(1)
            # Check active payments
            p = session.query(Payment).filter(Payment.reference == ref).first()
            if not p:
                # Check deleted payments
                dp = session.query(DeletedPayment).filter(DeletedPayment.reference == ref).first()
                if not dp:
                    ghosts.append({
                        'timestamp': l.timestamp,
                        'client_id': l.entity_id, # Usually logged here
                        'ref': ref,
                        'amount': float(amount_match.group(1)) if amount_match else 0.0,
                        'description': l.description
                    })
                    print(f"👻 FANTASMA ENCONTRADO: {l.timestamp} | Ref: {ref} | {l.description}")
    return ghosts

def check_balance_integrity():
    print("\n=== [2] VERIFICANDO INTEGRIDAD DE BALANCES vs FACTURAS ===")
    clients = session.query(Client).all()
    mismatches = []
    
    for c in clients:
        # Get total of unpaid invoices
        unpaid_sum = sum(inv.total_amount for inv in session.query(Invoice).filter(
            Invoice.client_id == c.id,
            Invoice.status == 'unpaid'
        ).all())
        
        balance = c.account_balance or 0.0
        
        if abs(balance - unpaid_sum) > 0.01:
            mismatches.append({
                'client_id': c.id,
                'name': c.legal_name,
                'balance': balance,
                'unpaid_sum': unpaid_sum,
                'diff': balance - unpaid_sum
            })
            print(f"⚖️ DESAJUSTE: {c.legal_name} (ID {c.id}) | Bal: {balance} | Invs: {unpaid_sum} | Diff: {balance - unpaid_sum}")
            
    return mismatches

def run_reconciliation():
    ghosts = find_ghost_payments()
    mismatches = check_balance_integrity()
    
    print("\n" + "="*50)
    print(f"RESUMEN FINAL:")
    print(f"- Pagos Fantasma: {len(ghosts)}")
    print(f"- Desajustes de Balance: {len(mismatches)}")
    print("="*50)

if __name__ == "__main__":
    try:
        run_reconciliation()
    finally:
        session.close()
