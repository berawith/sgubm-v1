import requests
import time

base_url = 'http://localhost:5000/api'
client_id = 594

def get_balance():
    r = requests.get(f'{base_url}/clients/{client_id}')
    return r.json()['account_balance']

print(f"Starting verification for client {client_id}")
initial_balance = get_balance()
print(f"Initial Balance: {initial_balance}")

# 1. Register a test payment
print("Registering test payment of 10000...")
r = requests.post(f'{base_url}/clients/{client_id}/payments', json={
    'amount': 10000,
    'payment_method': 'cash',
    'notes': 'VERIFICATION_TEST_PAYMENT',
    'authorized': True
})
if r.status_code != 201:
    print(f"FAILED to register payment: {r.status_code} {r.text}")
    exit(1)

balance_after_pay = get_balance()
print(f"Balance after payment: {balance_after_pay}")

# 2. Get the payment ID
r = requests.get(f'{base_url}/clients/{client_id}')
# Assuming the latest payment is the one we just made
# Or we can get it from the register response if it returns it
# Looking at payments_controller.py, create_payment returns the new payment dict

# Actually let's just get all payments for this client and find the latest
r = requests.get(f'{base_url}/payments?client_id={client_id}&limit=1')
payments = r.json()
if not payments or payments[0]['notes'] != 'VERIFICATION_TEST_PAYMENT':
    print("Could not find the test payment in the list.")
    exit(1)

payment_id = payments[0]['id']
print(f"Found test payment ID: {payment_id}")

# 3. Void (delete) the payment
print(f"Voiding payment {payment_id}...")
r = requests.delete(f'{base_url}/payments/{payment_id}?reason=VERIFICATION_VOID')
if r.status_code != 200:
    print(f"FAILED to void payment: {r.status_code} {r.text}")
    exit(1)

print("Payment voided successfully.")
final_balance = get_balance()
print(f"Final Balance after void: {final_balance}")

if final_balance == initial_balance:
    print("VERIFICATION SUCCESSFUL: Balance was restored correctly.")
else:
    print(f"VERIFICATION FAILED: Final balance {final_balance} != Initial balance {initial_balance}")
