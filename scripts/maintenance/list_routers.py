
from src.infrastructure.database.models import Router
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()
for r in session.query(Router).all():
    print(f"{r.id}: {r.alias}")
session.close()
