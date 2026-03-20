import sqlite3

conn = sqlite3.connect('pantry_pulse.db')
cur = conn.cursor()

# Check tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
print("Tables:", tables)

# Check store data
cur.execute('SELECT * FROM store')
stores = cur.fetchall()
print("\nStores:", stores)

# Check product data
cur.execute('SELECT * FROM product')
products = cur.fetchall()
print("\nProducts:", products)

# Check price entries
cur.execute('SELECT COUNT(*) FROM price_entry')
price_count = cur.fetchone()[0]
print(f"\nPrice entries count: {price_count}")

cur.execute('SELECT * FROM price_entry LIMIT 5')
prices = cur.fetchall()
print("First 5 price entries:", prices)

conn.close()
