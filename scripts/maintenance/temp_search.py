from run import create_app
from src.infrastructure.database.db_manager import get_db

app = create_app()
with app.app_context():
    db = get_db()
    repo = db.get_client_repository()
    # Buscamos de forma más amplia para evitar errores de tipeo
    results = repo.get_filtered(search='Isabel')
    for c in results:
        if 'Zambrano' in (c.legal_name or '') or 'Zambrano' in (c.username or ''):
            print(f"Nombre: {c.legal_name} | Usuario: {c.username} | IP: {c.ip_address} | MAC: {c.mac_address}")
