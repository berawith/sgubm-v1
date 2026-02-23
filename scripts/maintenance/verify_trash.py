import requests
import json

def test_archived_clients():
    base_url = "http://localhost:5000/api/clients"
    client_id = 268 # Isabel Zambrano
    
    print(f"--- Testing Archived Clients View Support ---")
    
    # 1. Check if client is in trash
    print(f"Checking if client {client_id} is in trash...")
    response = requests.get(f"{base_url}?status=deleted")
    if response.status_code == 200:
        clients = response.json()
        is_in_trash = any(c['id'] == client_id for c in clients)
        if is_in_trash:
            print(f"✅ Success: Client found in /api/clients?status=deleted")
        else:
            print(f"❌ Error: Client not found in trash listing")
    else:
        print(f"❌ Error: Failed to fetch trash list (Status: {response.status_code})")

    # 2. Check individual client status
    print(f"Checking individual client {client_id} status...")
    response = requests.get(f"{base_url}/{client_id}")
    if response.status_code == 200:
        client = response.json()
        print(f"✅ Success: Client status is '{client.get('status')}'")
    else:
        print(f"❌ Error: Failed to fetch client (Status: {response.status_code})")

if __name__ == "__main__":
    test_archived_clients()
