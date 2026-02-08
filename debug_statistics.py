
import sys
import os
from datetime import datetime, timedelta

# Añadir el path del proyecto
sys.path.append('c:/SGUBM-V1')

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import ClientStatus, PaymentStatus
from flask import Flask

app = Flask(__name__)

def test_statistics():
    print("Testing get_statistics logic...")
    try:
        db = get_db()
        payment_repo = db.get_payment_repository()
        
        # Copiando la lógica del controlador
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        print("Calculating totals...")
        today_total = payment_repo.get_total_by_date_range(today_start, now)
        print(f"Today: {today_total}")
        
        # ... recent payments
        recent_payments = payment_repo.get_all(limit=10)
        print(f"Recent: {len(recent_payments)}")
        
        # ... client metrics
        client_repo = db.get_client_repository()
        clients = client_repo.get_all()
        print(f"Clients: {len(clients)}")
        
        total_debt = sum(c.account_balance for c in clients if c.account_balance > 0)
        
        # Facturación esperada
        active_str = ClientStatus.ACTIVE.value if hasattr(ClientStatus.ACTIVE, 'value') else "active"
        monthly_billed_target = sum(
            c.monthly_fee for c in clients 
            if c.status == active_str or (hasattr(c.status, 'value') and c.status.value == active_str)
        )
        print(f"Target: {monthly_billed_target}")
        
        # Tendencia
        annual_trend = []
        for i in range(11, -1, -1):
            temp_date = now.replace(day=1)
            for _ in range(i):
                last_day_prev_month = temp_date - timedelta(days=1)
                temp_date = last_day_prev_month.replace(day=1)
            
            month_start_i = temp_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if i == 0:
                month_end_i = now
            else:
                next_month = (month_start_i + timedelta(days=32)).replace(day=1)
                month_end_i = next_month - timedelta(seconds=1)
            
            print(f"Checking {month_start_i.strftime('%Y-%m')}...")
            collected = payment_repo.get_total_by_date_range(month_start_i, month_end_i)
            
            annual_trend.append({
                'label': month_start_i.strftime('%b'),
                'collected': collected
            })
            
        print("Success! Logic is working fine.")
        
    except Exception as e:
        print(f"\n❌ ERROR DETECTED: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_statistics()
