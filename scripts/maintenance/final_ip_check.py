
from src.infrastructure.database.models import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

ips = ['177.77.70.9', '177.77.70.23', '77.16.10.239']
for ip in ips:
    print(f"IP {ip}:")
    cs = session.query(Client).filter(Client.ip_address == ip).all()
    for c in cs:
        print(f"  - ID {c.id}: {c.legal_name}")

session.close()
