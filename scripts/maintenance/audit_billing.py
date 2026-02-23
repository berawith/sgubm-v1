
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, Payment
from sqlalchemy import func
from datetime import datetime

def audit_billing_deep():
    db = get_db()
    session = db.session
    
    print("--- Deep Billing Audit ---")
    
    # 1. Invoice creation peak
    latest_invoices = session.query(Invoice.created_at, func.count(Invoice.id))\
        .group_by(Invoice.created_at)\
        .order_by(Invoice.created_at.desc()).limit(5).all()
    
    print("Latest Invoices (Timestamp, Count):")
    for ts, count in latest_invoices:
        print(f"  {ts}: {count}")
    
    # 2. Sample Client Breakdown
    sample_client = session.query(Client).first()
    if sample_client:
        print(f"\nSample Client: {sample_client.legal_name}")
        print(f"  Monthly Fee: {sample_client.monthly_fee}")
        print(f"  Account Balance: {sample_client.account_balance}")
        print(f"  Status: {sample_client.status}")
        
        invoices = session.query(Invoice).filter(Invoice.client_id == sample_client.id).all()
        print(f"  Invoices associated: {len(invoices)}")
        for inv in invoices:
            print(f"    - ID: {inv.id}, Issue: {inv.issue_date}, Total: {inv.total_amount}, Created: {inv.created_at}")

    # 3. Sum of Monthly Fees vs Sum of Balances
    sum_fees_all = session.query(func.sum(Client.monthly_fee)).scalar() or 0
    sum_fees_billing = session.query(func.sum(Client.monthly_fee)).filter(Client.status.in_(['active', 'suspended'])).scalar() or 0
    sum_balances = session.query(func.sum(Client.account_balance)).scalar() or 0
    feb_payments = session.query(func.sum(Payment.amount)).filter(Payment.payment_date >= datetime(2026, 2, 1)).scalar() or 0
    
    print(f"\nGlobal Totals:")
    print(f"  Sum All Monthly Fees (Total DB): {sum_fees_all:,.2f}")
    print(f"  Sum Fees (Active/Suspended): {sum_fees_billing:,.2f}")
    print(f"  Sum All Account Balances: {sum_balances:,.2f}")
    print(f"  Total Payments (Feb 2026): {feb_payments:,.2f}")
    
    expected = sum_fees_billing
    actual = sum_balances + feb_payments
    print(f"\nBilling Integrity Check:")
    print(f"  Target Revenue (Active/Suspended): {expected:,.2f}")
    print(f"  Current Value (Debt + Paid): {actual:,.2f}")
    print(f"  Integrity Gap: {expected - actual:,.2f}")
    
    if abs(expected - actual) < 0.01:
        print("✅ INTEGRITY VERIFIED: Billing matches precisely.")
    else:
        print("⚠️ INTEGRITY GAP: There is an unexplained difference.")
    
    # 4. Check for clients with balance but no invoices
    no_inv_debt = session.query(Client).filter(~Client.invoices.any(), Client.account_balance > 0).count()
    print(f"Clients with debt but NO invoices: {no_inv_debt}")
    
    # 5. Detailed Discrepancy Check
    print("\nClients with Discrepancies (Balance != Monthly Fee):")
    discrepancies = session.query(Client).filter(Client.account_balance != Client.monthly_fee, Client.status == 'active').all()
    total_diff = 0
    for c in discrepancies:
        inv_count = session.query(Invoice).filter(Invoice.client_id == c.id).count()
        pay_count = session.query(Payment).filter(Payment.client_id == c.id).count()
        print(f"  - {c.legal_name}: Balance {c.account_balance:,.0f} vs Fee {c.monthly_fee:,.0f} (Invoices: {inv_count}, Payments: {pay_count})")
        total_diff += (c.monthly_fee - c.account_balance)
    
    print(f"Total discrepancy found in active clients: {total_diff:,.2f}")

    # 6. Check for any invoices from Dec/Jan (different query style)
    any_old = session.query(Invoice).filter(Invoice.issue_date < datetime(2026, 2, 1)).count()
    print(f"\nInvoices before Feb 1st 2026: {any_old}")

if __name__ == "__main__":
    audit_billing_deep()
