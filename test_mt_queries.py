from routeros_api import RouterOsApiPool

# Connection details for Router 1
host = '12.12.12.1'
user = 'admin'
pw = 'b1382285**'
port = 8738

pool = RouterOsApiPool(host, username=user, password=pw, port=port, plaintext_login=True)
api = pool.get_api()

resource = api.get_resource('/interface')

try:
    ifaces = resource.call('print', {'.proplist': 'name'})
    
    # Test monitor-traffic on a specific interface
    print("\nTesting monitor-traffic on specific interface...")
    if ifaces:
        target_iface = ifaces[0].get('name')
        print(f"Polling interface: {target_iface}")
        traffic = resource.call('monitor-traffic', {'interface': target_iface, 'once': 'true'})
        print(f"Results: {len(traffic)} items")
        if traffic:
            print("Traffic sample:", traffic[0])
            
except Exception as e:
    print(f"Error: {e}")

# Test surgical print on /queue/simple
print("\nTesting surgical print on /queue/simple...")
try:
    queues = api.get_resource('/queue/simple').call('print', {'.proplist': 'name,target,rate'})
    print(f"Results: {len(queues)} items")
    if queues:
        print("First item keys:", list(queues[0].keys()))
        print("First item rate:", queues[0].get('rate'))
except Exception as e:
    print(f"Error: {e}")

pool.disconnect()
