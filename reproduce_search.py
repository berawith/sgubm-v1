from datetime import datetime
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment

# Initialize DB via Manager
db = get_db()
session = db.session
payment_repo = db.get_payment_repository()
client_repo = db.get_client_repository()

# 1. Create a dummy client and payment for testing
print("Creating test data...")
try:
    # Check if client exists
    code = 'SEARCH-TEST-01'
    client = session.query(Client).filter_by(subscriber_code=code).first()
    
    if not client:
        # Create directly if repo doesn't support complex create or for simplicity
        client = Client(
            router_id=1,
            subscriber_code=code,
            legal_name='Juan Pérez Buscador',
            status='active',
            ip_address='192.168.99.99'
        )
        session.add(client)
        session.commit()
    
    # Check if payment exists
    ref = 'REF-SEARCH-001'
    payment = session.query(Payment).filter_by(reference=ref).first()
    
    if not payment:
        payment = Payment(
            client_id=client.id,
            amount=50.0,
            payment_date=datetime.utcnow(),
            payment_method='cash',
            reference=ref,
            status='verified'
        )
        session.add(payment)
        session.commit()

    print(f"Created/Found Client: {client.legal_name} (ID: {client.id})")
    print(f"Created/Found Payment: {payment.id}")

    # 2. Test Search Exact
    print("\nTest 1: Exact Name Search ('Juan Pérez Buscador')")
    results = payment_repo.get_filtered(search='Juan Pérez Buscador')
    print(f"Results: {len(results)}")
    
    # 3. Test Search Partial
    print("\nTest 2: Partial Name Search ('Juan')")
    results = payment_repo.get_filtered(search='Juan')
    print(f"Results: {len(results)}")

    # 4. Test Search Case Insensitive Lower
    print("\nTest 3: Lowercase Name Search ('juan')")
    results = payment_repo.get_filtered(search='juan')
    print(f"Results: {len(results)}")

    # 5. Test Search Case Insensitive Upper
    print("\nTest 4: Uppercase Name Search ('JUAN')")
    results = payment_repo.get_filtered(search='JUAN')
    print(f"Results: {len(results)}")
    
    # 6. Test Search Reference
    print("\nTest 5: Reference Search ('REF-SEARCH')")
    results = payment_repo.get_filtered(search='REF-SEARCH')
    print(f"Results: {len(results)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.remove_session()
