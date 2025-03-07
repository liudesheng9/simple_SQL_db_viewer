import sqlite3
import os

# Create a test database in the current directory
db_path = 'test_database.db'

# Connect to SQLite database (it will be created if it doesn't exist)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    age INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
''')

# Create products table
cursor.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    category TEXT,
    stock INTEGER DEFAULT 0
)
''')

# Create orders table
cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    order_date TEXT DEFAULT CURRENT_TIMESTAMP,
    total_amount REAL,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users (id)
)
''')

# Insert sample data for users
users = [
    ('john_doe', 'john@example.com', 28),
    ('jane_smith', 'jane@example.com', 34),
    ('bob_johnson', 'bob@example.com', 42),
    ('alice_brown', 'alice@example.com', 23),
    ('charlie_davis', 'charlie@example.com', 31)
]

cursor.executemany('INSERT OR IGNORE INTO users (username, email, age) VALUES (?, ?, ?)', users)

# Insert sample data for products
products = [
    ('Laptop', 'High-performance laptop', 1299.99, 'Electronics', 10),
    ('Smartphone', 'Latest model', 899.99, 'Electronics', 15),
    ('Headphones', 'Noise-cancelling', 249.99, 'Electronics', 20),
    ('Coffee Maker', 'Automatic drip', 79.99, 'Kitchen', 5),
    ('Blender', 'High-speed blender', 129.99, 'Kitchen', 8),
    ('Running Shoes', 'Lightweight running shoes', 119.99, 'Clothing', 12),
    ('T-shirt', 'Cotton t-shirt', 24.99, 'Clothing', 50),
    ('Book', 'Bestseller novel', 19.99, 'Books', 30),
    ('Desk Chair', 'Ergonomic office chair', 299.99, 'Furniture', 7),
    ('Desk Lamp', 'LED desk lamp', 49.99, 'Furniture', 15)
]

cursor.executemany('INSERT OR IGNORE INTO products (name, description, price, category, stock) VALUES (?, ?, ?, ?, ?)', products)

# Insert sample data for orders
orders = [
    (1, '2023-01-15', 1299.99, 'completed'),
    (1, '2023-02-20', 249.99, 'completed'),
    (2, '2023-02-10', 899.99, 'completed'),
    (3, '2023-03-05', 129.99, 'completed'),
    (4, '2023-03-15', 144.98, 'shipped'),
    (5, '2023-04-02', 299.99, 'pending'),
    (2, '2023-04-10', 49.99, 'pending')
]

cursor.executemany('INSERT OR IGNORE INTO orders (user_id, order_date, total_amount, status) VALUES (?, ?, ?, ?)', orders)

# Commit changes and close connection
conn.commit()
conn.close()

# Get the absolute path for the user to copy
absolute_path = os.path.abspath(db_path)

print(f"Test database created at: {absolute_path}")
print("Sample tables created: users, products, orders")
print("\nYou can now use this path in the SQLite Viewer application.") 