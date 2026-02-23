import sqlite3
import sys

# Connect to database
conn = sqlite3.connect('sgubm.db')
cursor = conn.cursor()

# Query router ID 5
result = cursor.execute('''
    SELECT id, alias, host_address, api_port, api_username, status, last_error 
    FROM routers 
    WHERE id = 5
''').fetchone()

if result:
    print(f"Router ID: {result[0]}")
    print(f"Alias: {result[1]}")
    print(f"Host: {result[2]}")
    print(f"Port: {result[3]}")
    print(f"Username: {result[4]}")
    print(f"Status: {result[5]}")
    print(f"Last Error: {result[6]}")
else:
    print("Router ID 5 not found in database")

conn.close()
