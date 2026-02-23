import os
import sys
sys.path.append(os.getcwd())
from src.infrastructure.database.models import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def search_orphan_names():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    orphan_names = [
        'Zuleima Hernandez Palma Sola', 'GLORIA BERA', 'Wanda Aleta', 
        'Yilber Idalgo', 'MAIRA USECHE CASA BLANCA', 'Leidybaez', 
        'MailynMontilla', 'YulimarRangel', 'JhonGuarguati', 
        'CarmenRuiz', 'JuanitaOscatery', 'LeocadiaMora'
    ]
    
    print("\n--- Searching for Orphan Names in DB ---")
    for name in orphan_names:
        # Search in legal_name, username, identity_document, email
        results = session.query(Client).filter(
            Client.legal_name.like(f'%{name}%') | 
            Client.username.like(f'%{name}%') |
            Client.identity_document.like(f'%{name}%')
        ).all()
        
        if results:
            print(f"Found match for '{name}':")
            for c in results:
                print(f" - ID: {c.id} | Code: {c.subscriber_code} | Name: {c.legal_name} | User: {c.username}")
        else:
            # Try parts of the name
            parts = name.split()
            if len(parts) > 1:
                first_part = parts[0]
                results_part = session.query(Client).filter(
                    Client.legal_name.like(f'%{first_part}%') | 
                    Client.username.like(f'%{first_part}%')
                ).all()
                if results_part:
                    print(f"Partial matches for '{name}' (searching '{first_part}'):")
                    for c in results_part:
                        print(f" - ID: {c.id} | Name: {c.legal_name} | User: {c.username}")
                else:
                    print(f"No matches found for '{name}' or '{first_part}'")
            else:
                print(f"No matches found for '{name}'")

    session.close()

if __name__ == "__main__":
    search_orphan_names()
