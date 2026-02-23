
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, Invoice, AuditLog
from sqlalchemy import func
import json

def run_financial_audit():
    db = get_db()
    session = db.session
    
    print("=== FINANCIAL AUDIT REPORT ===")
    
    # 1. Total Summary
    total_clients = session.query(Client).count()
    total_payments = session.query(Payment).count()
    total_invoices = session.query(Invoice).count()
    total_unpaid_invoices = session.query(Invoice).filter(Invoice.status == 'unpaid').count()
    total_balance = session.query(func.sum(Client.account_balance)).scalar() or 0
    
    print(f"Total Clients: {total_clients}")
    print(f"Total Payments: {total_payments}")
    print(f"Total Invoices: {total_invoices}")
    print(f"Total Unpaid Invoices: {total_unpaid_invoices}")
    print(f"Total Portfolio Balance: ${total_balance:,.2f}")
    print("-" * 30)
    
    # 2. Balance Consistency Check (Simple FIFO check)
    print("Checking Balance Consistency (Balance vs Unpaid Invoices)...")
    inconsistent_clients = []
    
    # We check if account_balance matches sum of unpaid invoices
    # Note: BillingService sometimes resets balance, so we check if balance <= sum(unpaid)
    clients_with_balance = session.query(Client).filter(Client.account_balance > 0).all()
    for client in clients_with_balance:
        unpaid_sum = session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'unpaid'
        ).scalar() or 0
        
        if abs(client.account_balance - unpaid_sum) > 0.01:
            inconsistent_clients.append({
                'id': client.id,
                'name': client.legal_name,
                'balance': client.account_balance,
                'unpaid_sum': unpaid_sum,
                'diff': client.account_balance - unpaid_sum
            })
            
    print(f"Found {len(inconsistent_clients)} clients with balance discrepancies.")
    if inconsistent_clients:
        for item in inconsistent_clients[:10]:
            print(f"- Client {item['id']} ({item['name']}): Balance ${item['balance']} | Unpaid Sum ${item['unpaid_sum']} | Diff ${item['diff']}")
    print("-" * 30)
    
    # 3. Orphaned Records
    print("Checking for Orphaned Records...")
    orphaned_payments = session.query(Payment).filter(~Payment.client_id.in_(session.query(Client.id))).count()
    orphaned_invoices = session.query(Invoice).filter(~Invoice.client_id.in_(session.query(Client.id))).count()
    
    print(f"Orphaned Payments: {orphaned_payments}")
    print(f"Orphaned Invoices: {orphaned_invoices}")
    print("-" * 30)
    
    # 4. Audit Log Activity (Last 24h)
    print("Recent Financial Audit Activity (Last 50 logs):")
    recent_logs = session.query(AuditLog).filter(AuditLog.category == 'accounting').order_by(AuditLog.timestamp.desc()).limit(50).all()
    for log in recent_logs:
        print(f"[{log.timestamp}] {log.operation} - {log.description}")
        
    print("-" * 30)
    print("Audit Complete.")

if __name__ == "__main__":
    run_financial_audit()
