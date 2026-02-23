
import json
import requests
import random
import string
from datetime import datetime

BASE_URL = "http://localhost:5000/api"

def random_username():
    return "TestUser_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def test_smart_import():
    username = random_username()
    print(f"🚀 Testing Smart Import Logic with username: {username}")
    
    # Mock data for import
    import_payload = {
        "router_id": 1,
        "import_mode": "prorate",
        "clients": [
            {
                "username": username,
                "password": "testpassword",
                "ip_address": f"192.168.88.{random.randint(101, 254)}",
                "profile": "PLAN_15Mbps",
                "type": "pppoe",
                "status": "active",
                "mikrotik_id": f"*{random.randint(100, 999)}"
            }
        ]
    }
    
    try:
        # 1. Execute Import
        print(f"--- Executing Import (Mode: {import_payload['import_mode']}) ---")
        response = requests.post(f"{BASE_URL}/clients/execute-import", json=import_payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200 and response.json().get('imported', 0) > 0:
            # 2. Verify Client and Invoice
            print("\n--- Verifying Created Client and Invoice ---")
            clients_res = requests.get(f"{BASE_URL}/clients")
            clients = clients_res.json()
            
            test_client = next((c for c in clients if c['username'] == username), None)
            
            if test_client:
                print(f"✅ Client created with ID: {test_client['id']}")
                print(f"Balance: {test_client.get('account_balance')}")
                
                # Check invoices for this client
                invoices_res = requests.get(f"{BASE_URL}/billing/invoices?client_id={test_client['id']}")
                invoices = invoices_res.json()
                
                if invoices:
                    print(f"✅ Invoice(s) found: {len(invoices)}")
                    for inv in invoices:
                        print(f"  - Invoice ID: {inv['id']}, Amount: {inv['total_amount']}, Status: {inv['status']}")
                        # Check invoice description if possible (might need a specific endpoint or check items)
                else:
                    print("❌ No invoices found for the new client.")
            else:
                print(f"❌ Test client '{username}' not found in database.")
        else:
            print("❌ Import failed or client already exists.")
                
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    test_smart_import()
