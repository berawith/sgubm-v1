import requests
import json

def test_api():
    try:
        # We need to know the actual port, usually 5000
        url = "http://localhost:5000/api/clients?router_id=5"
        print(f"Testing URL: {url}")
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Count: {len(data)}")
        if len(data) > 0:
            print("First client sample:")
            print(json.dumps(data[0], indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
