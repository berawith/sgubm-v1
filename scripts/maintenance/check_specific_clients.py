import sys
import os
sys.path.append(os.getcwd())
from src.infrastructure.database.models import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

clients_to_check = ['Grabiela', 'Juan Pablo', 'Barrios']
for name_part in clients_to_check:
    clients = session.query(Client).filter(Client.legal_name.like(f'%{name_part}%')).all()
    if clients:
        for c in clients:
            print(f'Found: {c.legal_name} | Username: {c.username} | IP: {c.ip_address} | Status: {c.status} | Router ID: {c.router_id}')
    else:
        print(f'No client found with "{name_part}" in name.')

session.close()
