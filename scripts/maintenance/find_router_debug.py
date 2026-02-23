
from src.infrastructure.database.db_manager import get_db
from datetime import datetime, timedelta

def find_router_by_collected(target_amount, month, year):
    db = get_db()
    router_repo = db.get_router_repository()
    payment_repo = db.get_payment_repository()
    client_repo = db.get_client_repository()
    
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        
    routers = router_repo.get_all()
    print(f"Searching for amount: {target_amount}")
    
    for r in routers:
        # We need a way to filter payments by router. 
        # My previous fix added router_id to get_by_date_range.
        payments = payment_repo.get_by_date_range(start_date, end_date, router_id=r.id)
        total = sum(p.amount for p in payments)
        
        # Calculate pending for this router too
        clients = client_repo.get_filtered(router_id=r.id, status='ALL')
        pending = sum(c.account_balance for c in clients if (c.account_balance or 0) > 0 and c.status != 'deleted')
        
        print(f"Router: {r.alias} (ID: {r.id}) - Collected: {total}, Pending: {pending}")
        
if __name__ == "__main__":
    find_router_by_collected(2520000, 2, 2026)
