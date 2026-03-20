import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db():
    conn = sqlite3.connect('pantry_pulse.db')
    try:
        yield conn
    finally:
        conn.close()

# Drop and recreate store table without city column
with get_db() as conn:
    cur = conn.cursor()

    # Step 1: Drop old constraints if they exist
    cur.execute("ALTER TABLE price_entry RENAME TO price_entry_old")

    cur.execute("DROP TABLE store")

    # Step 2: Create new store table without city
    cur.execute("""
        CREATE TABLE store (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE
        )
    """)

    # Step 3: Insert stores
    stores = ['Tesco', 'Kaufland', 'Billa', 'Lidl']
    for i, store in enumerate(stores, 1):
        cur.execute("INSERT INTO store (id, name) VALUES (?, ?)", (i, store))

    # Step 4: Recreate price_entry table with correct store_id references
    cur.execute("DROP TABLE price_entry_old")

    cur.execute("""
        CREATE TABLE price_entry (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES product(id),
            FOREIGN KEY (store_id) REFERENCES store(id)
        )
    """)

    conn.commit()
    print("Database cleaned! Removed cities and duplicate stores.")
    print("Stores table recreated with unique constraint on name.")

# Verify the cleanup
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT * FROM store")
    print("\nStores after cleanup:", cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM price_entry")
    print("Price entries:", cur.fetchone()[0])
