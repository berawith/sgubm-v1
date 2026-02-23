
from src.infrastructure.database.models import Client, Invoice
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

search_term = "%Pernia%"
clients = session.query(Client).filter(Client.legal_name.ilike(search_term)).all()

print(f"--- REVISIÓN DE BALANCE PARA CLIENTES '{search_term}' ---")
for c in clients:
    unpaid_invoices = session.query(Invoice).filter(Invoice.client_id == c.id, Invoice.status == 'unpaid').all()
    debt = sum(i.total_amount for i in unpaid_invoices)
    print(f"ID: {c.id} | Name: {c.legal_name} | Balance DB: {c.account_balance} | Debt (Unpaid Inv): {debt}")
    if unpaid_invoices:
        for i in unpaid_invoices:
            print(f"  - Unpaid Invoice ID: {i.id} | Amount: {i.total_amount} | Date: {i.issue_date}")

session.close()
