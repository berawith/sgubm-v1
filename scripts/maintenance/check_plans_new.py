
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, InternetPlan

def check_plans():
    db = get_db()
    session = db.session
    new_ids = [591, 592, 593, 594]
    clients = session.query(Client).filter(Client.id.in_(new_ids)).all()
    
    print(f"--- Client Plans ---")
    for c in clients:
        plan = session.query(InternetPlan).filter(InternetPlan.id == c.plan_id).first()
        print(f"Client: {c.legal_name} (ID: {c.id}), PlanID: {c.plan_id}, PlanName: {plan.name if plan else 'N/A'}, Price: {plan.monthly_price if plan else 'N/A'}, ClientMonthlyFee: {c.monthly_fee}")

if __name__ == "__main__":
    check_plans()
