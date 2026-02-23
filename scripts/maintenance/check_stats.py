
import sys
import os
from datetime import datetime
sys.path.append(os.getcwd())
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Payment

def check_payment_stats():
    db = get_db()
    session = db.session
    stats = session.query(Payment.payment_date).all()
    
    date_counts = {}
    
    for (d,) in stats:
        date_str = d.strftime('%Y-%m-%d')
        date_counts[date_str] = date_counts.get(date_str, 0) + 1
        
    print("Date counts:", date_counts)
    db.remove_session()

if __name__ == "__main__":
    check_payment_stats()
