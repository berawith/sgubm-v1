"""
Verification Script: WhatsApp Agent Brain
Tests the logic without a real WhatsApp connection.
"""
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.db_manager import get_db
from src.application.services.whatsapp_agent_service import WhatsAppAgentService

def test_agent_logic():
    print("--- Testing WhatsApp Agent Brain ---")
    
    # 1. Setup DB Manager
    db_manager = get_db()
    agent = WhatsAppAgentService(db_manager)
    
    # 2. Get a client from the real DB
    client_repo = db_manager.get_client_repository()
    clients = client_repo.get_all()
    
    # Filter for clients with balance or specific status for better testing
    test_client = next((c for c in clients if c.phone), None)
    
    if not test_client:
        print("No test client with phone found in DB. Using a mockup.")
        from src.infrastructure.database.models import Client
        test_client = Client(legal_name="Juan Perez", phone="573001234567", account_balance=150000.0)

    phone = test_client.phone
    print(f"Testing with client: {test_client.legal_name} ({phone})")

    # 3. Test Scenarios
    scenarios = [
        "Hola, ¿cuánto debo?",
        "¿Cuándo es mi fecha de corte?",
        "El internet está muy lento",
        "Quiero saber mi saldo por favor"
    ]

    for msg in scenarios:
        print(f"\n[CLIENT]: {msg}")
        response = agent.process_incoming_message(phone, msg, client_override=test_client)
        print(f"[AGENT]: {response}")

if __name__ == "__main__":
    test_agent_logic()
