
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Invoice
from datetime import datetime

def fix_due_dates():
    db = get_db()
    session = db.session
    
    # Target date: 5th of Feb at 17:00
    new_due_date = datetime(2026, 2, 5, 17, 0, 0)
    
    print(f"🔧 Actualizando fechas de vencimiento a {new_due_date}...")
    
    invoices = session.query(Invoice).filter(Invoice.issue_date == datetime(2026, 2, 1)).all()
    updated = 0
    for inv in invoices:
        inv.due_date = new_due_date
        updated += 1
        
    session.commit()
    print(f"✅ Se han actualizado {updated} facturas.")

if __name__ == "__main__":
    fix_due_dates()
