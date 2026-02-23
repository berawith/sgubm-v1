import requests
import json

BASE_URL = "http://localhost:5000/api/reports"

def test_financial_report():
    print("🔍 Testing Financial Report (Annual)...")
    try:
        response = requests.get(f"{BASE_URL}/financial?period=annual")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Summary: {data['summary']}")
            print(f"Breakdown count: {len(data['breakdown'])}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

def test_clients_status_report():
    print("\n🔍 Testing Clients Status Report (Debtors)...")
    try:
        response = requests.get(f"{BASE_URL}/clients-status?type=debtors")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Count: {data['count']}")
            if data['clients']:
                print(f"First client: {data['clients'][0]['name']} - Balance: {data['clients'][0]['balance']}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

def test_missing_clients_report():
    print("\n🔍 Testing Missing Clients Report (Potential collection gap)...")
    try:
        response = requests.get(f"{BASE_URL}/clients-status?type=missing")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Missing count: {data['count']}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_financial_report()
    test_clients_status_report()
    test_missing_clients_report()
