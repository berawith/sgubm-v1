from src.infrastructure.database.db_manager import get_db
import sys

def main():
    try:
        db = get_db()
        client_repo = db.get_client_repository()
        clients = client_repo.get_all()
        
        debt_clients = [c for c in clients if (c.account_balance and c.account_balance > 0)]
        total_debt = sum(c.account_balance for c in debt_clients)
        
        print(f"Total Debt found in DB: {total_debt}")
        print("-" * 30)
        for c in debt_clients[:10]:
            print(f"- {c.legal_name}: ${c.account_balance}")
        
        if len(debt_clients) > 10:
            print(f"... and {len(debt_clients) - 10} more")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
