
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Payment, ClientTrafficHistory, PaymentPromise, DeletedPayment, Invoice, PendingOperation

def check_client_dependencies(client_id):
    db = get_db()
    session = db.session
    
    dependencies = {
        'Payments': Payment,
        'Traffic History': ClientTrafficHistory,
        'Payment Promises': PaymentPromise,
        'Deleted Payments': DeletedPayment,
        'Invoices': Invoice,
        'Pending Operations': PendingOperation
    }
    
    print(f"Checking dependencies for Client ID: {client_id}")
    for name, model in dependencies.items():
        count = session.query(model).filter(model.client_id == client_id).count()
        print(f"- {name}: {count}")

if __name__ == "__main__":
    check_client_dependencies(5)
